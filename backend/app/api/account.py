"""Account-level endpoints for NMI ownership and plan assignments."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db, init_db
from app.models.auth import User, UserNmi, UserNmiPlanAssignment
from app.models.invoice import Invoice
from app.models.meter_data import MeterDataInterval
from app.schemas.auth import (
    BillingGap,
    DashboardSummary,
    InvoiceSummaryItem,
    NmiCreateRequest,
    NmiLocationOut,
    NmiOut,
    NmiPlanAssignmentCreateRequest,
    NmiPlanAssignmentOut,
)
from app.services.auth_service import auth_service, get_current_user
from app.services.invoice_parser import InvoiceParser


router = APIRouter()
invoice_parser = InvoiceParser()


@router.get("/dashboard-summary", response_model=DashboardSummary)
def dashboard_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    init_db()

    # 1. Get user's NMIs
    user_nmis = db.query(UserNmi.nmi).filter(UserNmi.user_id == user.id).all()
    nmi_list = [row.nmi for row in user_nmis]

    if not nmi_list:
        return DashboardSummary(
            invoice_total=0,
            usage_kwh=0,
            controlled_load_kwh=0,
            solar_export_kwh=0,
        )

    # 2. Query all invoices for those NMIs belonging to this user
    all_invoices = (
        db.query(Invoice)
        .filter(
            Invoice.user_id == user.id,
            Invoice.nmi.in_(nmi_list),
            Invoice.billing_period_start.isnot(None),
            Invoice.billing_period_end.isnot(None),
        )
        .order_by(Invoice.created_at.desc())
        .all()
    )

    # 3. Deduplicate by (nmi, billing_period_start, billing_period_end) — keep latest by created_at
    seen: set[tuple[str, str, str]] = set()
    deduped: list[Invoice] = []
    for inv in all_invoices:
        key = (inv.nmi or "", inv.billing_period_start or "", inv.billing_period_end or "")
        if key not in seen:
            seen.add(key)
            deduped.append(inv)

    if not deduped:
        return DashboardSummary(
            invoice_total=0,
            usage_kwh=0,
            controlled_load_kwh=0,
            solar_export_kwh=0,
        )

    # 4. Sum totals
    invoice_total = sum(float(inv.total) for inv in deduped if inv.total is not None)

    # 5. Global billing period span
    def parse_date(s: str) -> date:
        return date.fromisoformat(s)

    all_starts = [parse_date(inv.billing_period_start) for inv in deduped if inv.billing_period_start]
    all_ends = [parse_date(inv.billing_period_end) for inv in deduped if inv.billing_period_end]
    period_start = min(all_starts)
    period_end = max(all_ends)

    # 6. Detect billing gaps — sort deduped invoices by period start, find gaps
    sorted_invoices = sorted(deduped, key=lambda i: parse_date(i.billing_period_start))
    billing_gaps: list[BillingGap] = []
    for idx in range(1, len(sorted_invoices)):
        prev_end = parse_date(sorted_invoices[idx - 1].billing_period_end)
        curr_start = parse_date(sorted_invoices[idx].billing_period_start)
        if prev_end + timedelta(days=1) < curr_start:
            billing_gaps.append(BillingGap(
                gap_start=prev_end + timedelta(days=1),
                gap_end=curr_start - timedelta(days=1),
            ))

    # 7. Build invoice summary items
    invoice_items = [
        InvoiceSummaryItem(
            invoice_number=inv.invoice_number,
            billing_period_start=parse_date(inv.billing_period_start),
            billing_period_end=parse_date(inv.billing_period_end),
            total=float(inv.total) if inv.total is not None else 0,
        )
        for inv in sorted_invoices
    ]

    # 8. Query meter data scoped to the billing period
    # CDR imports can create duplicate rows for the same interval — deduplicate
    # by (nmi, register_code, start_at) via a subquery first.
    deduped = (
        db.query(
            MeterDataInterval.profile_read_value,
            MeterDataInterval.rate_type_description,
        )
        .filter(
            MeterDataInterval.nmi.in_(nmi_list),
            MeterDataInterval.start_at >= period_start.isoformat(),
            MeterDataInterval.start_at < (period_end + timedelta(days=1)).isoformat(),
        )
        .group_by(
            MeterDataInterval.nmi,
            MeterDataInterval.register_code,
            MeterDataInterval.start_at,
        )
        .subquery()
    )

    # Usage = everything except Solar
    usage_row = (
        db.query(func.coalesce(func.sum(deduped.c.profile_read_value), 0))
        .filter(~deduped.c.rate_type_description.ilike("%Solar%"))
        .scalar()
    )

    # Controlled load
    controlled_row = (
        db.query(func.coalesce(func.sum(deduped.c.profile_read_value), 0))
        .filter(deduped.c.rate_type_description.ilike("%Controlledload%"))
        .scalar()
    )

    # Solar export
    solar_row = (
        db.query(func.coalesce(func.sum(deduped.c.profile_read_value), 0))
        .filter(deduped.c.rate_type_description.ilike("%Solar%"))
        .scalar()
    )

    return DashboardSummary(
        invoice_total=round(invoice_total, 2),
        billing_period_start=period_start,
        billing_period_end=period_end,
        billing_gaps=billing_gaps,
        usage_kwh=round(float(usage_row), 2),
        controlled_load_kwh=round(float(controlled_row), 2),
        solar_export_kwh=round(float(solar_row), 2),
        invoices=invoice_items,
    )


@router.get("/nmis", response_model=list[NmiOut])
def list_nmis(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    init_db()
    rows = db.query(UserNmi).filter(UserNmi.user_id == user.id).order_by(UserNmi.created_at.asc()).all()
    return [
        NmiOut(
            id=row.id,
            nmi=row.nmi,
            label=row.label,
            service_address=row.service_address,
            suburb=row.suburb,
            state=row.state,
            postcode=row.postcode,
            latitude=row.latitude,
            longitude=row.longitude,
            geocode_source=row.geocode_source,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/nmi-locations", response_model=list[NmiLocationOut])
async def list_nmi_locations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    init_db()
    rows = db.query(UserNmi).filter(UserNmi.user_id == user.id).order_by(UserNmi.created_at.asc()).all()
    usage_by_nmi = dict(
        db.query(MeterDataInterval.nmi, func.sum(MeterDataInterval.profile_read_value))
        .filter(MeterDataInterval.nmi.in_([r.nmi for r in rows]))
        .group_by(MeterDataInterval.nmi)
        .all()
    )
    latest_assignments = (
        db.query(UserNmiPlanAssignment)
        .join(UserNmi, UserNmiPlanAssignment.user_nmi_id == UserNmi.id)
        .filter(UserNmi.user_id == user.id)
        .order_by(UserNmiPlanAssignment.created_at.desc())
        .all()
    )
    latest_by_nmi: dict[str, UserNmiPlanAssignment] = {}
    for assignment in latest_assignments:
        nmi = assignment.user_nmi.nmi
        if nmi not in latest_by_nmi:
            latest_by_nmi[nmi] = assignment

    payload: list[NmiLocationOut] = []
    for row in rows:
        latest = latest_by_nmi.get(row.nmi)
        invoice_total = None
        invoice_number = None
        if latest and latest.source_invoice_file_id:
            invoice = await invoice_parser.get_invoice_with_fallback(latest.source_invoice_file_id, db)
            if invoice:
                total = invoice.get("total")
                invoice_total = float(total) if total is not None else None
                invoice_number = invoice.get("invoice_number")

        usage_raw = usage_by_nmi.get(row.nmi)
        usage_kwh = float(usage_raw) if usage_raw is not None else None
        payload.append(
            NmiLocationOut(
                id=row.id,
                nmi=row.nmi,
                service_address=row.service_address,
                suburb=row.suburb,
                state=row.state,
                postcode=row.postcode,
                latitude=row.latitude,
                longitude=row.longitude,
                geocode_source=row.geocode_source,
                usage_kwh=usage_kwh,
                latest_invoice_total=invoice_total,
                latest_invoice_number=invoice_number,
            )
        )
    return payload


@router.post("/nmis", response_model=NmiOut)
def add_nmi(payload: NmiCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    init_db()
    normalized = payload.nmi.strip().upper()
    if len(normalized) not in (10, 11):
        raise HTTPException(status_code=400, detail="NMI must be 10-11 characters")
    row = auth_service.get_or_create_user_nmi(db, user_id=user.id, nmi=normalized, label=payload.label)
    return NmiOut(id=row.id, nmi=row.nmi, label=row.label, created_at=row.created_at)


@router.get("/nmi-plan-assignments", response_model=list[NmiPlanAssignmentOut])
def list_nmi_plan_assignments(
    nmi: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    init_db()
    query = db.query(UserNmiPlanAssignment).join(UserNmi, UserNmiPlanAssignment.user_nmi_id == UserNmi.id).filter(UserNmi.user_id == user.id)
    if nmi:
        query = query.filter(UserNmi.nmi == nmi.strip().upper())
    rows = query.order_by(UserNmiPlanAssignment.effective_from.desc(), UserNmiPlanAssignment.created_at.desc()).all()
    return [
        NmiPlanAssignmentOut(
            id=row.id,
            nmi=row.user_nmi.nmi,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
            retailer_name=row.retailer_name,
            retail_plan_id=row.retail_plan_id,
            network_tariff_code=row.network_tariff_code,
            source_invoice_file_id=row.source_invoice_file_id,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/nmi-plan-assignments", response_model=NmiPlanAssignmentOut)
def add_nmi_plan_assignment(
    payload: NmiPlanAssignmentCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    init_db()
    row = auth_service.add_plan_assignment(
        db=db,
        user_id=user.id,
        nmi=payload.nmi,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        retailer_name=payload.retailer_name,
        retail_plan_id=payload.retail_plan_id,
        network_tariff_code=payload.network_tariff_code,
        source_invoice_file_id=payload.source_invoice_file_id,
    )
    return NmiPlanAssignmentOut(
        id=row.id,
        nmi=row.user_nmi.nmi,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        retailer_name=row.retailer_name,
        retail_plan_id=row.retail_plan_id,
        network_tariff_code=row.network_tariff_code,
        source_invoice_file_id=row.source_invoice_file_id,
        created_at=row.created_at,
    )
