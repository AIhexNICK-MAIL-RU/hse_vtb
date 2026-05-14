from __future__ import annotations

from typing import Any

import pandas as pd


def build_summary(df: pd.DataFrame, scenario: str, okrug: str | None) -> tuple[str, dict[str, Any]]:
    d = df if okrug is None or okrug == "" else df[df["okrug"].astype(str) == okrug]
    if d.empty:
        return (
            "Нет данных для выбранных фильтров (проверьте округ или загрузите датасет).",
            {"rows": 0},
        )

    scen_labels = {
        "white_spots": "белые пятна",
        "competitor": "перехват конкурента",
        "growth_retail": "динамика ТЦ/вузов (прокси по волатильности)",
        "low_utilization": "низкая загрузка существующих точек",
        "any": "все сценарии",
    }
    scen_name = scen_labels.get(scenario, scenario)

    if scenario != "any":
        d2 = d[d["scenario_tags"].apply(lambda tags: scenario in tags)]
        if d2.empty:
            d2 = d
    else:
        d2 = d

    top = d2.nlargest(5, "ml_score")
    mean_h = float(d2["heuristic_score"].mean())
    mean_ml = float(d2["ml_score"].mean())
    share_white = float(d2["scenario_tags"].apply(lambda t: "white_spots" in t).mean())
    share_comp = float(d2["scenario_tags"].apply(lambda t: "competitor" in t).mean())

    lines: list[str] = []
    lines.append(
        f"Краткий отчёт по сценарию «{scen_name}»"
        + (f" для округа {okrug}" if okrug else "")
        + f". Рассмотрено H3-зон: {len(d2)}."
    )
    lines.append(
        "Как читать цифры: геоиндекс H3 — ячейка гексагональной сетки для агрегатов. "
        "ML-приоритет (0–1) — выход модели RandomForest по псевдо-меткам от эвристики; "
        "им ранжируются зоны на карте. Эвристический Demand Score (0–1) — «сырой» спрос по правилам и признакам из CSV. "
        "Уникальные клиенты и сумма операций (₽) — фактические агрегаты в ячейке (объём спроса). "
        "Сценарные теги — бизнес-гипотезы (белые пятна, перехват конкурента и т.д.) по правилам; "
        "часть сигналов в статическом CSV заменена прокси-признаками (см. scenario_analysis.html)."
    )
    lines.append(
        f"Средний эвристический Demand Score: {mean_h:.3f}; "
        f"средний ML-приоритет (RandomForest по псевдо-меткам): {mean_ml:.3f}."
    )
    lines.append(
        f"Доля зон с тегом «белые пятна»: {share_white:.1%}; с тегом «перехват конкурента»: {share_comp:.1%}."
    )
    lines.append("Топ-5 зон по ML-приоритету:")
    for _, r in top.iterrows():
        tags = ", ".join(r["scenario_tags"]) if isinstance(r["scenario_tags"], list) else str(r["scenario_tags"])
        lines.append(
            f"  • {r['h3_index']} (H3): ML-приоритет={float(r['ml_score']):.3f}, "
            f"эвристический Demand Score={float(r['heuristic_score']):.3f}, "
            f"уникальные клиенты={int(r['unique_customers'])}, сумма операций={float(r['total_sum']):,.0f} ₽, "
            f"сценарные теги=[{tags}]"
        )
    risks: list[str] = []
    if float(d2["competitor_atm_count"].mean()) > 1.5:
        risks.append("в среднем высокая плотность конкурентных банкоматов — оцените эффект перехвата vs давление на маржу")
    if float(d2["vtb_atm_count"].mean()) > 0.8:
        risks.append("много зон уже с банкоматами ВТБ — риск каннибализации при новых установках")
    if risks:
        lines.append("Риски: " + "; ".join(risks) + ".")
    else:
        lines.append("Риски: выраженных аномалий по конкуренции/насыщению ВТБ в выборке не видно.")

    stats: dict[str, Any] = {
        "rows": int(len(d2)),
        "mean_heuristic": mean_h,
        "mean_ml": mean_ml,
        "share_white_spots": share_white,
        "share_competitor": share_comp,
        "top_h3": top["h3_index"].astype(str).tolist(),
    }
    return "\n".join(lines), stats
