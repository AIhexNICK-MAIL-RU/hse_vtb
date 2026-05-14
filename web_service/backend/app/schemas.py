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
    polygon: list[list[float]]  # GeoJSON ring: [lon, lat] pairs


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


class DevelopmentsResponse(BaseModel):
    count: int
    items: list[NewBuildingOut]
    geojson: dict[str, Any]
    source: str | None = None
