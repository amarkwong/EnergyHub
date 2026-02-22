"""Schemas for energy plans, catalog, and TOU alignment."""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Catalog-backed schemas (new)
# ---------------------------------------------------------------------------

class CatalogRetailerOut(BaseModel):
    slug: str
    name: str
    states: list[str] = []


class CatalogTouRateOut(BaseModel):
    name: str
    rate_cents_per_kwh: Optional[float] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    days: Optional[list[int]] = None


class CatalogFeedInTariffOut(BaseModel):
    unit_price_cents_per_kwh: Optional[float] = None
    name: Optional[str] = None
    type: Optional[str] = None
    period_name: Optional[str] = None
    time_from: Optional[str] = None
    time_to: Optional[str] = None
    tier_min_kwh: Optional[float] = None
    tier_max_kwh: Optional[float] = None
    tier_inferred: Optional[bool] = None


class CatalogPlanOut(BaseModel):
    idx: int
    retailer_slug: str
    retailer: str
    plan_name: str
    tariff_type: str
    customer_type: Optional[str] = None
    effective_from: Optional[str] = None
    daily_supply_charge_cents: Optional[float] = None
    usage_rate_cents_per_kwh: Optional[float] = None
    tou_rates: list[CatalogTouRateOut] = []
    feed_in_tariffs: list[CatalogFeedInTariffOut] = []
    distributors: list[str] = []
    state: Optional[str] = None
    plan_ids: list[str] = []
    source_url: Optional[str] = None


class CatalogStatusOut(BaseModel):
    version: Optional[int] = None
    generated_at_utc: Optional[str] = None
    retailer_count: int = 0
    plan_count: int = 0
    postcode_count: int = 0


# ---------------------------------------------------------------------------
# Legacy DB-backed schemas (kept for tou/tariffs routers)
# ---------------------------------------------------------------------------

class RetailerOut(BaseModel):
    id: int
    name: str
    slug: str
    source_url: Optional[str] = None
    states: list[str] = []


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


# ---------------------------------------------------------------------------
# TOU Alignment schemas (used by tou router)
# ---------------------------------------------------------------------------

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
