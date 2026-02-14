"""Account-level endpoints for NMI ownership and plan assignments."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db, init_db
from app.models.auth import User, UserNmi, UserNmiPlanAssignment
from app.models.meter_data import MeterDataInterval
from app.schemas.auth import (
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
            invoice = await invoice_parser.get_invoice(latest.source_invoice_file_id)
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
