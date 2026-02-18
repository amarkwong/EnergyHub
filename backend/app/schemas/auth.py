"""Schemas for authentication and account/NMI ownership."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


AccountType = Literal["residential", "business"]


class UserOut(BaseModel):
    id: int
    email: str
    account_type: AccountType
    display_name: Optional[str] = None
    created_at: datetime


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8, max_length=128)
    account_type: AccountType
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=1, max_length=128)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


class NmiCreateRequest(BaseModel):
    nmi: str = Field(..., min_length=10, max_length=11)
    label: Optional[str] = Field(default=None, max_length=128)


class NmiOut(BaseModel):
    id: int
    nmi: str
    label: Optional[str] = None
    service_address: Optional[str] = None
    suburb: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geocode_source: Optional[str] = None
    created_at: datetime


class NmiLocationOut(BaseModel):
    id: int
    nmi: str
    service_address: Optional[str] = None
    suburb: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geocode_source: Optional[str] = None
    usage_kwh: Optional[float] = None
    latest_invoice_total: Optional[float] = None
    latest_invoice_number: Optional[str] = None


class NmiPlanAssignmentCreateRequest(BaseModel):
    nmi: str = Field(..., min_length=10, max_length=11)
    effective_from: date
    effective_to: Optional[date] = None
    retailer_name: Optional[str] = None
    retail_plan_id: Optional[int] = None
    network_tariff_code: Optional[str] = None
    source_invoice_file_id: Optional[str] = None


class NmiPlanAssignmentOut(BaseModel):
    id: int
    nmi: str
    effective_from: date
    effective_to: Optional[date] = None
    retailer_name: Optional[str] = None
    retail_plan_id: Optional[int] = None
    network_tariff_code: Optional[str] = None
    source_invoice_file_id: Optional[str] = None
    created_at: datetime


class BillingGap(BaseModel):
    gap_start: date
    gap_end: date


class InvoiceSummaryItem(BaseModel):
    invoice_number: Optional[str] = None
    billing_period_start: date
    billing_period_end: date
    total: float


class DashboardSummary(BaseModel):
    invoice_total: float
    billing_period_start: Optional[date] = None
    billing_period_end: Optional[date] = None
    billing_gaps: list[BillingGap] = []
    usage_kwh: float
    controlled_load_kwh: float
    solar_export_kwh: float
    invoices: list[InvoiceSummaryItem] = []
