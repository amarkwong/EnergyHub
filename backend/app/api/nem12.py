"""NEM12 file upload and processing endpoints."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db, init_db
from app.models.meter_data import MeterDataInterval
from app.schemas.nem12 import NEM12UploadResponse, MeterData, ConsumptionSummary, RetailerCsvUploadResponse
from app.services.nem12_service import NEM12Service
from app.services.retailer_csv_meter_service import RetailerCsvMeterService

router = APIRouter()
nem12_service = NEM12Service()
retailer_csv_meter_service = RetailerCsvMeterService()


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
            processed_at=datetime.now(timezone.utc)
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
    end_date: str = None,
    db: Session = Depends(get_db),
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
        init_db()
        query = db.query(MeterDataInterval).filter(MeterDataInterval.file_id == file_id)
        if nmi:
            query = query.filter(MeterDataInterval.nmi == nmi)
        if start_date:
            query = query.filter(MeterDataInterval.start_at >= datetime.fromisoformat(f"{start_date} 00:00:00"))
        if end_date:
            query = query.filter(MeterDataInterval.start_at <= datetime.fromisoformat(f"{end_date} 23:59:59"))

        rows = query.order_by(MeterDataInterval.start_at.asc()).all()
        data = []
        for item in rows:
            minutes_since_midnight = item.start_at.hour * 60 + item.start_at.minute
            interval_number = (minutes_since_midnight // item.interval_length_minutes) + 1
            data.append(
                {
                    "nmi": item.nmi,
                    "date": item.start_at.date().isoformat(),
                    "interval": interval_number,
                    "interval_length_minutes": item.interval_length_minutes,
                    "value": float(item.profile_read_value),
                    "register_code": item.register_code,
                    "rate_type_description": item.rate_type_description,
                    "quality_flag": item.quality_flag,
                }
            )

    if not data:
        raise HTTPException(status_code=404, detail="No data found")
    return data


@router.post("/upload-retailer-csv", response_model=RetailerCsvUploadResponse)
async def upload_retailer_csv_meter_data(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload retailer-exported interval CSV and persist rows into meter_data_intervals."""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file type. Expected .csv")

    init_db()
    content = await file.read()
    file_id = str(uuid.uuid4())
    try:
        result = retailer_csv_meter_service.ingest(db, file_id=file_id, content=content.decode("utf-8"))
        return RetailerCsvUploadResponse(
            file_id=result.file_id,
            filename=file.filename,
            rows_inserted=result.rows_inserted,
            nmi_count=result.nmi_count,
            register_count=result.register_count,
            interval_length_minutes=result.interval_length_minutes,
            start_at=result.start_at,
            end_at=result.end_at,
            processed_at=datetime.now(timezone.utc),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse retailer CSV file: {exc}") from exc
