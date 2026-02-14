"""Ingest interval CSV exports from retailers into meter_data_intervals."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO

from sqlalchemy.orm import Session

from app.models.meter_data import MeterDataInterval


CSV_DT_FMT = "%d/%m/%Y %I:%M:%S %p"
REQUIRED_COLUMNS = {
    "AccountNumber",
    "NMI",
    "DeviceNumber",
    "DeviceType",
    "RegisterCode",
    "RateTypeDescription",
    "StartDate",
    "EndDate",
    "ProfileReadValue",
    "RegisterReadValue",
    "QualityFlag",
}


@dataclass
class RetailerCsvIngestResult:
    file_id: str
    rows_inserted: int
    nmi_count: int
    register_count: int
    interval_length_minutes: int
    start_at: datetime
    end_at: datetime


class RetailerCsvMeterService:
    """Parser and persistence layer for non-NEM12 interval CSV exports."""

    def ingest(self, db: Session, file_id: str, content: str) -> RetailerCsvIngestResult:
        reader = csv.DictReader(StringIO(content))
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")

        reader.fieldnames = [self._normalize_header(h) for h in reader.fieldnames]
        missing = REQUIRED_COLUMNS.difference(set(reader.fieldnames))
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")

        db.query(MeterDataInterval).filter(MeterDataInterval.file_id == file_id).delete()
        db.flush()

        rows: list[MeterDataInterval] = []
        nmis: set[str] = set()
        registers: set[str] = set()
        start_min: datetime | None = None
        end_max: datetime | None = None
        interval_length_minutes = 30

        for raw in reader:
            row = {self._normalize_header(k): (v or "") for k, v in raw.items() if k is not None}
            start_at = self._parse_datetime(row["StartDate"])
            end_at = self._parse_datetime(row["EndDate"])
            if end_at < start_at:
                raise ValueError(f"EndDate before StartDate for row start={row['StartDate']} end={row['EndDate']}")

            profile_read = self._parse_decimal(row["ProfileReadValue"], field_name="ProfileReadValue")
            register_read = self._parse_decimal_optional(row["RegisterReadValue"])
            interval_length_minutes = max(1, int(((end_at - start_at).total_seconds() + 1) // 60))

            nmi = (row.get("NMI") or "").strip()
            register_code = (row.get("RegisterCode") or "").strip()
            nmis.add(nmi)
            if register_code:
                registers.add(register_code)

            rows.append(
                MeterDataInterval(
                    file_id=file_id,
                    source_format="retailer_csv",
                    account_number=(row.get("AccountNumber") or "").strip() or None,
                    nmi=nmi,
                    device_number=(row.get("DeviceNumber") or "").strip() or None,
                    device_type=(row.get("DeviceType") or "").strip() or None,
                    register_code=register_code or None,
                    rate_type_description=(row.get("RateTypeDescription") or "").strip() or None,
                    start_at=start_at,
                    end_at=end_at,
                    interval_length_minutes=interval_length_minutes,
                    profile_read_value=profile_read,
                    register_read_value=register_read,
                    quality_flag=(row.get("QualityFlag") or "").strip() or None,
                )
            )

            if start_min is None or start_at < start_min:
                start_min = start_at
            if end_max is None or end_at > end_max:
                end_max = end_at

        if not rows:
            raise ValueError("CSV file has no data rows")

        db.bulk_save_objects(rows)
        db.commit()

        return RetailerCsvIngestResult(
            file_id=file_id,
            rows_inserted=len(rows),
            nmi_count=len(nmis),
            register_count=len(registers),
            interval_length_minutes=interval_length_minutes,
            start_at=start_min or rows[0].start_at,
            end_at=end_max or rows[-1].end_at,
        )

    @staticmethod
    def _parse_datetime(raw: str) -> datetime:
        value = (raw or "").strip()
        if not value:
            raise ValueError("Missing datetime value in CSV row")
        return datetime.strptime(value, CSV_DT_FMT)

    @staticmethod
    def _parse_decimal(raw: str, field_name: str) -> Decimal:
        value = (raw or "").strip()
        if value == "":
            raise ValueError(f"Missing numeric value for {field_name}")
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid decimal for {field_name}: {raw}") from exc

    @staticmethod
    def _parse_decimal_optional(raw: str) -> Decimal | None:
        value = (raw or "").strip()
        if value == "":
            return None
        try:
            return Decimal(value)
        except InvalidOperation:
            return None

    @staticmethod
    def _normalize_header(value: str | None) -> str:
        return (value or "").strip().lstrip("\ufeff")
