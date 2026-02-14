"""TOU alignment service."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.energy_plan import TouDefinition, TouPeriod
from app.schemas.energy_plan import TouAlignInput


class TouService:
    """Resolve TOU periods and align interval data to local tariff windows."""

    def get_definition(
        self,
        db: Session,
        scope_type: str,
        scope_key: str,
        at_date: date,
        plan_id: int | None = None,
    ) -> TouDefinition | None:
        query = (
            db.query(TouDefinition)
            .filter(TouDefinition.scope_type == scope_type, TouDefinition.scope_key == scope_key)
            .filter(TouDefinition.effective_from <= at_date)
            .filter((TouDefinition.effective_to.is_(None)) | (TouDefinition.effective_to >= at_date))
        )
        if plan_id is not None:
            query = query.filter(TouDefinition.plan_id == plan_id)
        return query.order_by(TouDefinition.effective_from.desc()).first()

    def align_intervals(self, definition: TouDefinition, intervals: list[TouAlignInput]) -> tuple[list[dict], int]:
        periods = sorted(definition.periods, key=lambda p: p.priority)
        tz_name = definition.timezone
        tz = ZoneInfo(tz_name)

        aligned: list[dict] = []
        unmatched = 0
        for interval in intervals:
            local_dt = self._local_interval_datetime(interval, tz)
            period = self._match_period(local_dt, periods)
            if not period:
                unmatched += 1
                aligned.append(
                    {
                        "interval_date": interval.interval_date,
                        "interval_number": interval.interval_number,
                        "local_time": local_dt.strftime("%H:%M"),
                        "timezone": tz_name,
                        "period_name": "unmatched",
                        "unit": "kWh",
                        "value": interval.value,
                        "rate_cents_per_kwh": None,
                        "demand_rate_cents_per_kva": None,
                    }
                )
                continue

            aligned.append(
                {
                    "interval_date": interval.interval_date,
                    "interval_number": interval.interval_number,
                    "local_time": local_dt.strftime("%H:%M"),
                    "timezone": tz_name,
                    "period_name": period.name,
                    "unit": period.unit,
                    "value": interval.value,
                    "rate_cents_per_kwh": period.rate_cents_per_kwh,
                    "demand_rate_cents_per_kva": period.demand_rate_cents_per_kva,
                }
            )
        return aligned, unmatched

    @staticmethod
    def _local_interval_datetime(interval: TouAlignInput, tz: ZoneInfo) -> datetime:
        base = datetime(interval.interval_date.year, interval.interval_date.month, interval.interval_date.day, tzinfo=tz)
        minutes = (interval.interval_number - 1) * interval.interval_length_minutes
        return base + timedelta(minutes=minutes)

    @staticmethod
    def _match_period(local_dt: datetime, periods: list[TouPeriod]) -> TouPeriod | None:
        weekday = local_dt.weekday()
        current = local_dt.time()
        for period in periods:
            days = {int(x) for x in period.days_of_week.split(",") if x.strip() != ""}
            if weekday not in days:
                continue

            start = period.start_time
            end = period.end_time
            if start <= end:
                if start <= current < end:
                    return period
            else:
                # Overnight window (e.g. 21:00-07:00)
                if current >= start or current < end:
                    return period
        return None
