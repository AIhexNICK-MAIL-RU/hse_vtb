from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.schemas import (
    DevelopmentsResponse,
    ExplainFeature,
    ExplainResponse,
    HealthResponse,
    IngestResponse,
    NewBuildingOut,
    PlacementOut,
    RetrainResponse,
    SummaryResponse,
    ZoneOut,
    ZonesResponse,
)
from app.services.developments import developments_geojson
from app.services.features import FEATURE_COLUMNS, h3_to_polygon_geojson
from app.services.poi_distances import build_placement_payload, poi_layers_to_geojson
from app.services.summary import build_summary
from app.state import state

# В проде (Timeweb): GEOATM_API_PREFIX=/api + статика; локально с Vite — префикс пустой (прокси срезает /api).
API_PREFIX = os.environ.get("GEOATM_API_PREFIX", "").strip().rstrip("/")
STATIC_DIR = Path(os.environ.get("GEOATM_STATIC_DIR", "").strip())


def _row_to_zone(r: Any, placement: PlacementOut | None = None) -> ZoneOut:
    tags = r["scenario_tags"] if isinstance(r["scenario_tags"], list) else []
    poly = h3_to_polygon_geojson(str(r["h3_index"]))
    return ZoneOut(
        h3_index=str(r["h3_index"]),
        lat=float(r["lat"]),
        lon=float(r["lon"]),
        heuristic_score=float(r["heuristic_score"]),
        ml_score=float(r["ml_score"]),
        cluster_id=int(r["cluster_id"]),
        scenario_tags=[str(t) for t in tags],
        total_sum=float(r["total_sum"]),
        unique_customers=int(r["unique_customers"]),
        vtb_atm_count=int(r["vtb_atm_count"]),
        competitor_atm_count=int(r["competitor_atm_count"]),
        metro_count=int(r["metro_count"]),
        mall_count=int(r["mall_count"]),
        university_count=int(r["university_count"]),
        polygon=poly,
        placement=placement,
    )


def _health_response() -> HealthResponse:
    loaded = state.loaded()
    return HealthResponse(
        status="ok" if loaded else "degraded",
        data_loaded=loaded,
        rows=int(len(state.df)) if state.df is not None else 0,
        model_version=state.model_version,
        developments_count=len(state.developments),
        developments_source=(state.developments_meta or {}).get("source"),
        last_error=None if loaded else state.last_error,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Тяжёлый ingest не блокирует приём TCP/HTTP — иначе healthcheck PaaS падает по таймауту."""
    auto = os.environ.get("GEOATM_AUTO_INGEST", "1").lower() in {"1", "true", "yes"}
    if auto:

        def _ingest_sync() -> None:
            try:
                state.ingest(settings.data_dir)
            except Exception as e:  # noqa: BLE001
                state.last_error = str(e)

        asyncio.create_task(asyncio.to_thread(_ingest_sync))
    yield


_docs = f"{API_PREFIX}/docs" if API_PREFIX else "/docs"
_openapi = f"{API_PREFIX}/openapi.json" if API_PREFIX else "/openapi.json"

app = FastAPI(
    title="VTB GeoATM Analytics",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=_docs,
    openapi_url=_openapi,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("GEOATM_CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health_liveness() -> HealthResponse:
    """Корень: для healthcheck Paaс (до SPA mount, чтобы путь не перехватывался статикой)."""
    return _health_response()


@app.head("/health", include_in_schema=False)
def health_liveness_head() -> Response:
    """Timeweb и др. часто шлют HEAD; без явного маршрута FastAPI отдаёт 404."""
    return Response(status_code=200)


@app.get("/live", include_in_schema=False)
def live_probe() -> PlainTextResponse:
    """Самый дешёвый liveness для Docker/PaaS: без Pydantic и без обращения к state (ingest может грузить CPU)."""
    return PlainTextResponse("ok", media_type="text/plain")


@app.head("/live", include_in_schema=False)
def live_probe_head() -> Response:
    return Response(status_code=200)


router = APIRouter()

if API_PREFIX:

    @router.get("/health", response_model=HealthResponse)
    def health_api() -> HealthResponse:
        return _health_response()


@router.post("/ingest", response_model=IngestResponse)
def ingest(data_dir: str | None = Query(default=None)) -> IngestResponse:
    root = Path(data_dir) if data_dir else settings.data_dir
    try:
        state.ingest(root)
        assert state.df is not None
        return IngestResponse(
            ok=True,
            message="Данные загружены и модель переобучена.",
            rows=int(len(state.df)),
            model_version=state.model_version,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/developments", response_model=DevelopmentsResponse)
def get_developments() -> DevelopmentsResponse:
    """Новостройки: отдельный delivery_score по сроку сдачи (файл `new_buildings.csv` или GEOATM_NEW_BUILDINGS_CSV)."""
    items = [NewBuildingOut.model_validate(x) for x in state.developments]
    gj = developments_geojson(state.developments)
    src = (state.developments_meta or {}).get("source")
    return DevelopmentsResponse(count=len(items), items=items, geojson=gj, source=str(src) if src else None)


@router.get("/poi/geojson")
def poi_geojson() -> dict[str, Any]:
    """Точечные слои POI для карты (конкуренты, метро, ВТБ, офисы и т.д.)."""
    if not state.loaded():
        raise HTTPException(status_code=503, detail="Данные не загружены.")
    return poi_layers_to_geojson(state.poi or {})


@router.get("/zones", response_model=ZonesResponse)
def zones(
    scenario: str = Query(default="any"),
    okrug: str | None = Query(default=None),
    min_lon: float | None = None,
    min_lat: float | None = None,
    max_lon: float | None = None,
    max_lat: float | None = None,
    min_score: float | None = Query(default=None, description="Порог по эвристическому Demand Score"),
    min_ml: float | None = Query(default=None),
    limit: int = Query(default=300, ge=1, le=3000),
    include_placement: bool = Query(
        default=False,
        description="Добавить расстояния до POI, окружность (radius_m) и текст зоны размещения АТМ",
    ),
) -> ZonesResponse:
    if not state.loaded() or state.df is None:
        raise HTTPException(status_code=503, detail="Данные не загружены. Вызовите POST /ingest.")
    df = state.df
    d = df
    if okrug:
        d = d[d["okrug"].astype(str) == okrug]
    if scenario != "any":
        d = d[d["scenario_tags"].apply(lambda tags: scenario in tags)]
    if min_score is not None:
        d = d[d["heuristic_score"] >= float(min_score)]
    if min_ml is not None:
        d = d[d["ml_score"] >= float(min_ml)]
    if None not in (min_lon, min_lat, max_lon, max_lat):
        d = d[
            (d["lon"] >= min_lon)
            & (d["lon"] <= max_lon)
            & (d["lat"] >= min_lat)
            & (d["lat"] <= max_lat)
        ]
    d = d.sort_values("ml_score", ascending=False).head(limit)
    rad = int(settings.merged_config.get("ui", {}).get("placement_radius_m", 400))
    zones_out: list[ZoneOut] = []
    for _, r in d.iterrows():
        pl: PlacementOut | None = None
        if include_placement and state.poi is not None:
            raw_tags = r["scenario_tags"]
            if isinstance(raw_tags, list):
                tags_list = [str(x) for x in raw_tags]
            elif hasattr(raw_tags, "tolist"):
                tags_list = [str(x) for x in raw_tags.tolist()]
            else:
                tags_list = []
            raw_pl = build_placement_payload(
                float(r["lat"]),
                float(r["lon"]),
                str(r["h3_index"]),
                state.poi,
                radius_m=rad,
                ml_score=float(r["ml_score"]),
                heuristic_score=float(r["heuristic_score"]),
                scenario_tags=tags_list,
            )
            pl = PlacementOut.model_validate(raw_pl)
        zones_out.append(_row_to_zone(r, pl))
    return ZonesResponse(model_version=state.model_version, count=len(zones_out), zones=zones_out)


@router.get("/zones/{h3}/explain", response_model=ExplainResponse)
def explain_zone(h3: str) -> ExplainResponse:
    from app.services.ml_train import local_explain_row

    if not state.loaded() or state.df is None or state.bundle is None:
        raise HTTPException(status_code=503, detail="Данные не загружены.")
    df = state.df
    row = df.loc[df["h3_index"].astype(str) == h3]
    if row.empty:
        raise HTTPException(status_code=404, detail="H3 не найден")
    r = row.iloc[0]
    clf = state.bundle["classifier"]
    is_classifier = bool(state.bundle.get("is_classifier", True))
    impacts = local_explain_row(clf, is_classifier, df, h3, FEATURE_COLUMNS)
    feats = [ExplainFeature(feature=n, impact=v, direction=d) for n, v, d in impacts]

    parts = [
        f"Зона {h3}: эвристический DS={float(r['heuristic_score']):.3f}, ML-скор={float(r['ml_score']):.3f}, "
        f"кластер KMeans={int(r['cluster_id'])}."
    ]
    if feats:
        top = feats[0]
        parts.append(
            f"Наибольший вклад в ML-скор даёт признак «{top.feature}» (локальное объяснение заменой на медиану)."
        )
    if int(r["competitor_atm_count"]) >= 2 and int(r["vtb_atm_count"]) == 0:
        parts.append("Риск/возможность: сильное присутствие конкурентов при отсутствии ВТБ — сценарий перехвата.")
    if int(r["vtb_atm_count"]) >= 1 and float(r["sum_per_customer"]) < float(df["sum_per_customer"].median()):
        parts.append("Сигнал: при наличии ВТБ относительно низкий оборот на клиента — проверить загрузку точки.")
    narrative = " ".join(parts)

    tags = r["scenario_tags"] if isinstance(r["scenario_tags"], list) else []
    return ExplainResponse(
        model_version=state.model_version,
        h3_index=h3,
        heuristic_score=float(r["heuristic_score"]),
        ml_score=float(r["ml_score"]),
        cluster_id=int(r["cluster_id"]),
        scenario_tags=[str(t) for t in tags],
        top_features=feats,
        narrative=narrative,
    )


@router.get("/summary", response_model=SummaryResponse)
def summary(
    scenario: str = Query(default="any"),
    okrug: str | None = Query(default=None),
) -> SummaryResponse:
    if not state.loaded() or state.df is None:
        raise HTTPException(status_code=503, detail="Данные не загружены.")
    text, stats = build_summary(state.df, scenario, okrug)
    return SummaryResponse(model_version=state.model_version, scenario=scenario, okrug=okrug, text=text, stats=stats)


@router.post("/retrain", response_model=RetrainResponse)
def retrain(x_retrain_token: str | None = Header(default=None, alias="X-Retrain-Token")) -> RetrainResponse:
    token_cfg = str(settings.merged_config.get("security", {}).get("retrain_token", "dev-change-me"))
    env_tok = os.environ.get("GEOATM_RETRAIN_TOKEN")
    expected = env_tok or token_cfg
    if x_retrain_token != expected:
        raise HTTPException(status_code=401, detail="Неверный токен переобучения.")
    try:
        state.ingest(settings.data_dir)
        return RetrainResponse(
            ok=True,
            message="Переобучение выполнено.",
            model_version=state.model_version,
            metrics=dict(state.bundle.get("metrics", {})) if state.bundle else {},
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e


# --- регистрация API: с префиксом /api (прод) или без (локально + Vite proxy) ---
if API_PREFIX:
    app.include_router(router, prefix=API_PREFIX)
else:
    app.include_router(router)


@app.get("/", include_in_schema=False, response_model=None)
def root_spa_or_probe() -> FileResponse | PlainTextResponse:
    """Главная SPA. Путь проверки состояния «/» в Timeweb — стабильный 200 (GET)."""
    if STATIC_DIR.is_dir():
        index = STATIC_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
    return PlainTextResponse("ok", media_type="text/plain")


@app.head("/", include_in_schema=False)
def root_probe_head() -> Response:
    """HEAD «/» для healthcheck (Timeweb)."""
    return Response(status_code=200)


if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="spa")
