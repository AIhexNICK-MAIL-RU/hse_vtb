from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ScenarioId = Literal["white_spots", "competitor", "growth_retail", "low_utilization", "any"]


class HealthResponse(BaseModel):
    status: str = "ok"
    data_loaded: bool
    rows: int
    model_version: str
    developments_count: int = 0
    developments_source: str | None = None
    last_error: str | None = Field(
        default=None,
        description="Текст последней ошибки ingest (только пока data_loaded=false)",
    )


class NearestPoiOut(BaseModel):
    name: str = ""
    lat: float
    lon: float
    distance_m: int


class PlacementOut(BaseModel):
    """Контекст зоны размещения АТМ: радиус оценки и ближайшие POI (метры по геодезии)."""

    radius_m: int = 400
    summary: str = ""
    competitors_in_radius: int = 0
    nearest_metro: NearestPoiOut | None = None
    nearest_mall: NearestPoiOut | None = None
    nearest_market: NearestPoiOut | None = None
    nearest_hardware: NearestPoiOut | None = None
    nearest_university: NearestPoiOut | None = None
    nearest_office: NearestPoiOut | None = None
    nearest_vtb_atm: NearestPoiOut | None = None
    nearest_competitor_atm: NearestPoiOut | None = None


class ZoneOut(BaseModel):
    h3_index: str
    lat: float
    lon: float
    heuristic_score: float
    ml_score: float
    cluster_id: int
    scenario_tags: list[str]
    total_sum: float
    unique_customers: int
    vtb_atm_count: int
    competitor_atm_count: int
    metro_count: int
    mall_count: int
    university_count: int
    retention_proxy_score: float = Field(
        ...,
        description="Прокси удержания 0–1: уникальные клиенты, чек, частота, стабильность (низкая волатильность avg_std)",
    )
    competition_pressure_score: float = Field(
        ...,
        description="Давление среды 0–1: конкурентные АТМ + плотность метро (транзитные узлы)",
    )
    profile_tags: list[str] = Field(
        default_factory=list,
        description="Профиль ячейки: transit_retail_hub, stable_demand, competitive_corridor",
    )
    polygon: list[list[float]]  # GeoJSON ring: [lon, lat] pairs
    placement: PlacementOut | None = Field(
        default=None,
        description="Заполняется при include_placement=1: расстояния до POI и текст про зону размещения",
    )


class ZonesResponse(BaseModel):
    model_version: str
    count: int
    zones: list[ZoneOut]


class ExplainFeature(BaseModel):
    feature: str
    impact: float
    direction: str  # "up" | "down"


class ExplainResponse(BaseModel):
    model_version: str
    h3_index: str
    heuristic_score: float
    ml_score: float
    cluster_id: int
    scenario_tags: list[str]
    top_features: list[ExplainFeature]
    narrative: str


class SummaryResponse(BaseModel):
    model_version: str
    scenario: str
    okrug: str | None
    text: str
    stats: dict[str, Any]


class IngestResponse(BaseModel):
    ok: bool
    message: str
    rows: int
    model_version: str


class RetrainResponse(BaseModel):
    ok: bool
    message: str
    model_version: str
    metrics: dict[str, Any]


class NewBuildingOut(BaseModel):
    building_id: str
    name: str
    address: str
    lat: float
    lon: float
    completion_date: str
    delivery_score: float
    delivery_tier: str
    months_to_completion: float
    apartments: int | None = Field(
        default=None,
        description="Количество квартир из spisok_domov.csv (если указано)",
    )


class DevelopmentsResponse(BaseModel):
    count: int
    items: list[NewBuildingOut]
    geojson: dict[str, Any]
    source: str | None = None
