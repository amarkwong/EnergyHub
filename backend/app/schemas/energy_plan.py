"""Schemas for energy plans and TOU alignment."""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class RetailerOut(BaseModel):
    id: int
    name: str
    slug: str
    source_url: Optional[str] = None


class EnergyPlanOut(BaseModel):
    id: int
    retailer: str
    retailer_slug: str
    plan_name: str
    network_provider: Optional[str] = None
    tariff_type: str
    effective_from: date
    effective_to: Optional[date] = None
    daily_supply_charge_cents: Decimal
    usage_rate_cents_per_kwh: Optional[Decimal] = None
    feed_in_tariff_cents_per_kwh: Optional[Decimal] = None
    feed_in_tariffs: list[dict] = []
    source_url: Optional[str] = None
    is_active: bool


class TouPeriodOut(BaseModel):
    id: int
    name: str
    start_time: time
    end_time: time
    days_of_week: list[int]
    rate_cents_per_kwh: Optional[Decimal] = None
    demand_rate_cents_per_kva: Optional[Decimal] = None
    unit: str
    priority: int


class TouDefinitionOut(BaseModel):
    id: int
    scope_type: str
    scope_key: str
    name: str
    timezone: str
    source_url: Optional[str] = None
    effective_from: date
    effective_to: Optional[date] = None
    plan_id: Optional[int] = None
    periods: list[TouPeriodOut]


class EnergyPlanRefreshResponse(BaseModel):
    retailers: int
    plans: int
    tou_definitions: int
    tou_periods: int


class EmeFetchRequest(BaseModel):
    retailers: list[str] = Field(default_factory=lambda: ["agl", "origin", "energyaustralia"])
    page_size: int = Field(20, ge=1, le=100)
    max_plans_per_retailer: int = Field(0, ge=0, le=10000)
    fuel_type: str = Field("ELECTRICITY", pattern="^(ALL|ELECTRICITY|GAS)$")
    timeout_seconds: float = Field(30.0, ge=1.0, le=120.0)
    persist_to_retail_catalog: bool = True
    refresh_db_after_persist: bool = True
    refresh_network_tariffs: bool = False


class EmeFetchResponse(BaseModel):
    output_file: str
    plans_fetched: int
    retailers_requested: int
    stats: dict[str, dict]
    retail_catalog_persisted: bool
    retail_catalog_file: Optional[str] = None
    retail_catalog_stats: Optional[dict[str, int]] = None
    db_refresh: Optional[EnergyPlanRefreshResponse] = None
    cadence_months: int = 6
    recommended_eventbridge_cron: str
    next_recommended_run_utc: str
    network_tariffs_refreshed: bool = False
    network_tariff_log_lines: Optional[int] = None


class EmeFetchAllRetailersRequest(BaseModel):
    dropdown_html: str = Field(..., min_length=50, description="Retailer dropdown HTML from Energy Made Easy")
    source_url: str = Field(
        "https://www.energymadeeasy.gov.au/plans/electricity/current-energy-company",
        description="Source page URL for retailer dropdown",
    )
    page_size: int = Field(20, ge=1, le=100)
    max_plans_per_retailer: int = Field(0, ge=0, le=10000)
    fuel_type: str = Field("ELECTRICITY", pattern="^(ALL|ELECTRICITY|GAS)$")
    timeout_seconds: float = Field(30.0, ge=1.0, le=120.0)
    persist_to_retail_catalog: bool = True
    refresh_db_after_persist: bool = True
    refresh_network_tariffs: bool = False


CDR_REGISTRY_URL = "https://jxeeno.github.io/energy-cdr-prd-endpoints/energy-prd-endpoints.json"


class EmeFetchRegistryRequest(BaseModel):
    registry_url: str = Field(CDR_REGISTRY_URL, description="URL of the jxeeno CDR endpoint registry JSON")
    page_size: int = Field(20, ge=1, le=100)
    max_plans_per_retailer: int = Field(0, ge=0, le=10000)
    fuel_type: str = Field("ELECTRICITY", pattern="^(ALL|ELECTRICITY|GAS)$")
    timeout_seconds: float = Field(30.0, ge=1.0, le=120.0)
    persist_to_retail_catalog: bool = True
    refresh_db_after_persist: bool = True
    refresh_network_tariffs: bool = False


class EmeFetchAllRetailersResponse(BaseModel):
    output_file: str
    retailers_discovered: int
    retailers_resolved: int
    retailers_unresolved: int
    resolved_retailers: list[dict[str, str]]
    unresolved_retailers: list[dict]
    plans_fetched: int
    stats: dict[str, dict]
    retail_catalog_persisted: bool
    retail_catalog_file: Optional[str] = None
    retail_catalog_stats: Optional[dict[str, int]] = None
    db_refresh: Optional[EnergyPlanRefreshResponse] = None
    cadence_months: int = 6
    recommended_eventbridge_cron: str
    next_recommended_run_utc: str
    network_tariffs_refreshed: bool = False
    network_tariff_log_lines: Optional[int] = None


class TouAlignInput(BaseModel):
    interval_date: date
    interval_number: int = Field(..., ge=1, le=288)
    interval_length_minutes: int = Field(30, ge=1, le=60)
    value: Optional[float] = None


class TouAlignRequest(BaseModel):
    scope_type: str = Field(..., description="retailer or network")
    scope_key: str = Field(..., description="Retailer slug or network provider code")
    effective_date: Optional[date] = None
    plan_id: Optional[int] = None
    intervals: list[TouAlignInput]


class TouAlignedInterval(BaseModel):
    interval_date: date
    interval_number: int
    local_time: str
    timezone: str
    period_name: str
    unit: str
    value: Optional[float] = None
    rate_cents_per_kwh: Optional[Decimal] = None
    demand_rate_cents_per_kva: Optional[Decimal] = None


class TouAlignResponse(BaseModel):
    definition_id: int
    definition_name: str
    aligned_count: int
    unmatched_count: int
    intervals: list[TouAlignedInterval]


class TouAlignFileRequest(BaseModel):
    file_id: str
    scope_type: str = Field(..., description="retailer or network")
    scope_key: str = Field(..., description="Retailer slug or network provider code")
    effective_date: Optional[date] = None
    plan_id: Optional[int] = None
    nmi: Optional[str] = None
