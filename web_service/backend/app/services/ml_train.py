from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from app.services.features import FEATURE_COLUMNS, white_spot_thresholds


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    xr = pd.Series(x).rank(method="average").to_numpy(dtype=float)
    yr = pd.Series(y).rank(method="average").to_numpy(dtype=float)
    if len(xr) < 2:
        return float("nan")
    r = np.corrcoef(xr, yr)[0, 1]
    return float(r)


def _kendall_tau(x: np.ndarray, y: np.ndarray) -> float:
    """Упрощённый τ через scipy при наличии колёс; иначе NaN (см. docs)."""
    try:
        from scipy.stats import kendalltau

        t, _ = kendalltau(x, y)
        return float(t)
    except Exception:  # noqa: BLE001
        return float("nan")


def build_pseudo_labels(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.Series:
    """Псевдо-разметка: приоритет размещения (1) vs фон (0) по согласованным правилам."""
    ds_thr, uc_thr = white_spot_thresholds(df, cfg)
    scen = cfg.get("scenarios", {})
    comp_min = int(scen.get("competitor_min_atms", 2))

    vtb = df["vtb_atm_count"].astype(int)
    atm_act = df.get("atm_activity", pd.Series(0, index=df.index)).fillna(0).astype(int)
    uc = df["unique_customers"].astype(float)
    h = df["heuristic_score"].astype(float)
    comp = df["competitor_atm_count"].astype(int)

    pos_white = (vtb == 0) & (atm_act == 0) & (uc >= uc_thr) & (h >= ds_thr)
    pos_comp = (vtb == 0) & (comp >= comp_min) & (h >= 0.45)
    positive = pos_white | pos_comp

    negative = (h < 0.35) | ((vtb >= 3) & (h < 0.55))
    y = np.where(positive, 1, np.where(negative, 0, -1))  # -1 ambiguous

    # drop ambiguous for training
    return pd.Series(y, index=df.index, name="pseudo_y")


def train_models(df: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    ml_cfg = cfg.get("ml", {})
    rs = int(ml_cfg.get("random_state", 42))
    n_clusters = int(ml_cfg.get("n_clusters", 6))
    boot_iters = int(ml_cfg.get("bootstrap_iterations", 8))
    train_frac = float(ml_cfg.get("train_fraction", 0.85))

    X = df[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(float)
    y_raw = build_pseudo_labels(df, cfg)
    mask = y_raw >= 0
    X_t = X.loc[mask]
    y = y_raw.loc[mask].astype(int)
    if y.nunique() < 2 or len(y) < 50:
        # fallback: classify top heuristic as positive
        med = float(df["heuristic_score"].median())
        y = (df["heuristic_score"] >= med).astype(int)
        X_t = X
        mask = pd.Series(True, index=df.index)

    X_train, X_test, y_train, y_test = train_test_split(
        X_t, y, train_size=train_frac, random_state=rs, stratify=y if y.nunique() > 1 else None
    )

    clf: BaseEstimator
    is_classifier = True
    try:
        clf = RandomForestClassifier(
            n_estimators=120,
            max_depth=12,
            min_samples_leaf=3,
            random_state=rs,
            class_weight="balanced_subsample",
            n_jobs=-1,
        )
        clf.fit(X_train, y_train)
        if not hasattr(clf, "predict_proba"):
            raise RuntimeError("no proba")
        proba = clf.predict_proba(X)[:, 1]
        ml_score = pd.Series(proba, index=X.index).reindex(df.index).fillna(0.0)
    except Exception:  # noqa: BLE001
        is_classifier = False
        reg = RandomForestRegressor(
            n_estimators=120,
            max_depth=12,
            min_samples_leaf=3,
            random_state=rs,
            n_jobs=-1,
        )
        target = df.loc[X_train.index, "heuristic_score"].astype(float)
        reg.fit(X_train, target)
        clf = reg
        pred = reg.predict(X)
        s = pd.Series(pred, index=X.index, dtype=float)
        ml_score = ((s - s.min()) / (s.max() - s.min() + 1e-9)).reindex(df.index).fillna(0.0)

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X.values)
    km = KMeans(n_clusters=n_clusters, random_state=rs, n_init="auto")
    clusters = km.fit_predict(Xs)

    # metrics vs heuristic
    h = df["heuristic_score"].astype(float)
    sp = _spearman(ml_score.values, h.values)
    kd = _kendall_tau(ml_score.values, h.values)
    auc = float("nan")
    if is_classifier and y_test.nunique() > 1:
        try:
            auc = float(roc_auc_score(y_test, clf.predict_proba(X_test)[:, 1]))
        except ValueError:
            auc = float("nan")

    # coverage@k: share of pseudo-positive in top-k by ml_score
    k = max(50, int(0.05 * len(df)))
    top_idx = ml_score.nlargest(k).index
    cov = float(df.loc[top_idx].assign(_y=(y_raw.reindex(df.index).fillna(0) == 1).astype(int))["_y"].mean())

    # permutation importance (global, on test)
    if is_classifier:
        r = permutation_importance(
            clf, X_test, y_test, n_repeats=5, random_state=rs, n_jobs=1
        )
    else:
        yh = df.loc[X_test.index, "heuristic_score"].astype(float)
        r = permutation_importance(
            clf,
            X_test,
            yh,
            n_repeats=5,
            random_state=rs,
            n_jobs=1,
            scoring="neg_mean_squared_error",
        )
    perm_order = np.argsort(-r.importances_mean)
    perm_feats = [FEATURE_COLUMNS[i] for i in perm_order[:8]]
    perm_vals = [float(r.importances_mean[i]) for i in perm_order[:8]]

    # bootstrap rank stability of ml vs heuristic
    rng = np.random.default_rng(rs)
    taus = []
    n = len(df)
    for _ in range(boot_iters):
        idx = rng.choice(n, size=int(0.8 * n), replace=True)
        t = _kendall_tau(ml_score.values[idx], h.values[idx])
        if np.isfinite(t):
            taus.append(float(t))
    tau_boot_std = float(np.std(taus)) if taus else float("nan")

    return {
        "classifier": clf,
        "is_classifier": is_classifier,
        "scaler": scaler,
        "kmeans": km,
        "ml_score": ml_score,
        "cluster_id": pd.Series(clusters, index=df.index, name="cluster_id"),
        "metrics": {
            "spearman_ml_vs_heuristic": float(sp) if np.isfinite(sp) else None,
            "kendall_ml_vs_heuristic": float(kd) if np.isfinite(kd) else None,
            "roc_auc_holdout_pseudo": float(auc) if np.isfinite(auc) else None,
            "coverage_at_topk_pseudo_positive": cov,
            "k_top": k,
            "kendall_bootstrap_std": tau_boot_std,
            "n_train": int(len(X_train)),
            "n_test": int(len(X_test)),
            "model_head": "RandomForestClassifier" if is_classifier else "RandomForestRegressor(heuristic)",
        },
        "permutation_top_features": list(zip(perm_feats, perm_vals, strict=False)),
    }


def local_explain_row(
    clf: BaseEstimator,
    is_classifier: bool,
    df_full: pd.DataFrame,
    h3: str,
    feature_names: list[str],
) -> list[tuple[str, float, str]]:
    row = df_full.loc[df_full["h3_index"].astype(str) == h3]
    if row.empty:
        return []
    x0 = row.iloc[0][feature_names].replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(float).to_frame().T

    def _score(frame: pd.DataFrame) -> float:
        if is_classifier:
            return float(clf.predict_proba(frame)[0, 1])
        pred = float(clf.predict(frame)[0])
        s = df_full[feature_names].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        preds = clf.predict(s)
        lo, hi = float(np.min(preds)), float(np.max(preds))
        return (pred - lo) / (hi - lo + 1e-9)

    base_p = _score(x0)
    medians = df_full[feature_names].median(numeric_only=True)
    impacts: list[tuple[str, float, str]] = []
    for name in feature_names:
        x1 = x0.copy()
        x1[name] = float(medians[name])
        p1 = _score(x1)
        delta = p1 - base_p
        direction = "down" if delta < 0 else "up"
        impacts.append((name, float(base_p - p1), direction))  # positive = feature supports high score
    impacts.sort(key=lambda t: abs(t[1]), reverse=True)
    return impacts[:8]
