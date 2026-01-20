"""NEM12 file upload and processing endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, HTTPException

from app.schemas.nem12 import NEM12UploadResponse, MeterData, ConsumptionSummary
from app.services.nem12_service import NEM12Service

router = APIRouter()
nem12_service = NEM12Service()


@router.post("/upload", response_model=NEM12UploadResponse)
async def upload_nem12(file: UploadFile = File(...)):
    """
    Upload and process a NEM12 file.

    The NEM12 file will be parsed and stored for later use in
    invoice calculation and reconciliation.
    """
    if not file.filename.endswith(('.csv', '.txt', '.nem12')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Expected .csv, .txt, or .nem12"
        )

    content = await file.read()
    file_id = str(uuid.uuid4())

    try:
        meters = await nem12_service.process_nem12(file_id, content.decode('utf-8'))
        total_intervals = sum(m.get('interval_count', 0) for m in meters)

        return NEM12UploadResponse(
            file_id=file_id,
            filename=file.filename,
            meters=[MeterData(**m) for m in meters],
            total_intervals=total_intervals,
            processed_at=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse NEM12 file: {str(e)}")


@router.get("/{file_id}/summary", response_model=list[ConsumptionSummary])
async def get_consumption_summary(file_id: str):
    """Get consumption summary for a processed NEM12 file."""
    summaries = await nem12_service.get_consumption_summary(file_id)
    if not summaries:
        raise HTTPException(status_code=404, detail="File not found or not processed")
    return summaries


@router.get("/{file_id}/intervals")
async def get_interval_data(
    file_id: str,
    nmi: str = None,
    start_date: str = None,
    end_date: str = None
):
    """
    Get raw interval data for charting.

    Returns interval readings that can be used to render consumption charts.
    """
    data = await nem12_service.get_interval_data(
        file_id,
        nmi=nmi,
        start_date=start_date,
        end_date=end_date
    )
    if not data:
        raise HTTPException(status_code=404, detail="No data found")
    return data
