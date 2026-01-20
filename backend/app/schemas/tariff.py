"""Tariff schemas for network and retail pricing."""
from datetime import date, time
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class NetworkProvider(str, Enum):
    """Australian electricity network distributors."""

    # ACT
    EVOENERGY = "evoenergy"

    # Queensland
    ERGON_ENERGY = "ergon_energy"
    ENERGEX = "energex"

    # New South Wales
    AUSGRID = "ausgrid"
    ESSENTIAL_ENERGY = "essential_energy"
    ENDEAVOUR_ENERGY = "endeavour_energy"

    # Victoria
    AUSNET_SERVICES = "ausnet_services"
    POWERCOR = "powercor"
    JEMENA = "jemena"
    CITIPOWER = "citipower"
    UNITED_ENERGY = "united_energy"

    # Tasmania
    TASNETWORKS = "tasnetworks"


class TariffType(str, Enum):
    """Types of electricity tariffs."""

    FLAT = "flat"  # Single rate all day
    TOU = "tou"  # Time of use (peak/off-peak/shoulder)
    DEMAND = "demand"  # Demand-based pricing
    CONTROLLED_LOAD = "controlled_load"  # Controlled load (hot water, etc.)


class TimePeriod(BaseModel):
    """Time period for TOU tariffs."""

    name: str  # e.g., "peak", "off_peak", "shoulder"
    start_time: time
    end_time: time
    days: list[int] = Field(default=[0, 1, 2, 3, 4, 5, 6], description="0=Monday, 6=Sunday")
    rate_cents_per_kwh: Decimal


class SeasonalPeriod(BaseModel):
    """Seasonal period for tariffs that vary by season."""

    name: str  # e.g., "summer", "winter"
    start_month: int = Field(..., ge=1, le=12)
    end_month: int = Field(..., ge=1, le=12)
    time_periods: list[TimePeriod]


class NetworkTariff(BaseModel):
    """Network (distribution) tariff structure."""

    tariff_code: str
    tariff_name: str
    network_provider: NetworkProvider
    tariff_type: TariffType
    effective_from: date
    effective_to: Optional[date] = None

    # Supply charge
    daily_supply_charge_cents: Decimal

    # Usage charges (for flat tariffs)
    usage_rate_cents_per_kwh: Optional[Decimal] = None

    # TOU periods (for TOU tariffs)
    time_periods: Optional[list[TimePeriod]] = None

    # Seasonal variations
    seasonal_periods: Optional[list[SeasonalPeriod]] = None

    # Demand charges
    demand_rate_cents_per_kw: Optional[Decimal] = None
    demand_threshold_kw: Optional[float] = None


class RetailTariff(BaseModel):
    """Retail energy tariff (energy component)."""

    retailer: str
    plan_name: str
    tariff_type: TariffType
    effective_from: date
    effective_to: Optional[date] = None

    # Supply charge
    daily_supply_charge_cents: Decimal

    # Usage charges
    usage_rate_cents_per_kwh: Optional[Decimal] = None
    time_periods: Optional[list[TimePeriod]] = None

    # Feed-in tariff (for solar export)
    feed_in_rate_cents_per_kwh: Optional[Decimal] = None

    # Discounts
    pay_on_time_discount_percent: Optional[Decimal] = None
    direct_debit_discount_percent: Optional[Decimal] = None


class TariffSearchRequest(BaseModel):
    """Request to search for tariffs."""

    network_provider: Optional[NetworkProvider] = None
    tariff_type: Optional[TariffType] = None
    effective_date: Optional[date] = None


class TariffResponse(BaseModel):
    """Response containing tariff data."""

    network_tariff: NetworkTariff
    last_updated: date
    source_url: Optional[str] = None
