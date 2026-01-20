"""NEM12 data schemas."""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class IntervalReading(BaseModel):
    """Single interval reading from NEM12 data."""

    nmi: str = Field(..., description="National Metering Identifier")
    interval_date: date
    interval_number: int = Field(..., ge=1, le=288)  # Max 288 for 5-min intervals
    value: float
    quality_flag: Optional[str] = None
    unit_of_measure: str = "kWh"


class MeterData(BaseModel):
    """Meter data summary from NEM12 file."""

    nmi: str
    meter_serial: Optional[str] = None
    register_id: str
    interval_length: int = Field(..., description="Interval length in minutes (5, 15, or 30)")
    unit_of_measure: str
    start_date: date
    end_date: date
    total_consumption: float
    total_generation: Optional[float] = None


class NEM12UploadResponse(BaseModel):
    """Response after uploading NEM12 file."""

    file_id: str
    filename: str
    meters: list[MeterData]
    total_intervals: int
    processed_at: datetime


class ConsumptionSummary(BaseModel):
    """Aggregated consumption summary."""

    nmi: str
    period_start: date
    period_end: date
    total_kwh: float
    peak_kwh: float
    off_peak_kwh: float
    shoulder_kwh: Optional[float] = None
    demand_kw: Optional[float] = None  # Maximum demand
