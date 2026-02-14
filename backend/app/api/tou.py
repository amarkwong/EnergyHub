"""TOU alignment endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.energy_plan import (
    TouAlignFileRequest,
    TouAlignInput,
    TouAlignRequest,
    TouAlignResponse,
)
from app.services.nem12_service import NEM12Service
from app.services.tou_service import TouService


router = APIRouter()
tou_service = TouService()
nem12_service = NEM12Service()


@router.post("/align", response_model=TouAlignResponse)
def align_tou(request: TouAlignRequest, db: Session = Depends(get_db)):
    at_date = request.effective_date or date.today()
    definition = tou_service.get_definition(
        db=db,
        scope_type=request.scope_type,
        scope_key=request.scope_key,
        at_date=at_date,
        plan_id=request.plan_id,
    )
    if not definition:
        raise HTTPException(status_code=404, detail="No matching TOU definition found")

    aligned, unmatched = tou_service.align_intervals(definition, request.intervals)
    return TouAlignResponse(
        definition_id=definition.id,
        definition_name=definition.name,
        aligned_count=len(aligned),
        unmatched_count=unmatched,
        intervals=aligned,
    )


@router.post("/align-file", response_model=TouAlignResponse)
async def align_tou_for_file(request: TouAlignFileRequest, db: Session = Depends(get_db)):
    at_date = request.effective_date or date.today()
    definition = tou_service.get_definition(
        db=db,
        scope_type=request.scope_type,
        scope_key=request.scope_key,
        at_date=at_date,
        plan_id=request.plan_id,
    )
    if not definition:
        raise HTTPException(status_code=404, detail="No matching TOU definition found")

    intervals = await nem12_service.get_interval_data(file_id=request.file_id, nmi=request.nmi)
    if not intervals:
        raise HTTPException(status_code=404, detail="No interval data found for file")

    align_inputs = [
        TouAlignInput(
            interval_date=item["date"],
            interval_number=item["interval"],
            interval_length_minutes=item.get("interval_length_minutes", 30),
            value=item.get("value"),
        )
        for item in intervals
    ]

    aligned, unmatched = tou_service.align_intervals(definition, align_inputs)
    return TouAlignResponse(
        definition_id=definition.id,
        definition_name=definition.name,
        aligned_count=len(aligned),
        unmatched_count=unmatched,
        intervals=aligned,
    )
