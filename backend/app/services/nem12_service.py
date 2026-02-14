"""NEM12 file processing service."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from app.db.database import SessionLocal
from app.models.meter_data import MeterDataInterval


class NEM12Service:
    """Service for processing NEM12 metering data files."""
    _shared_file_data: dict = {}

    def __init__(self):
        # Shared in-memory store across service instances.
        self._file_data = self._shared_file_data

    async def process_nem12(self, file_id: str, content: str) -> list[dict]:
        """
        Parse NEM12 file content and extract meter data.

        NEM12 format (AEMO specification):
        - 100: Header record
        - 200: NMI data details
        - 300: Interval data
        - 400: Interval event
        - 500: B2B details (optional)
        - 900: End of data

        Returns list of meter data summaries.
        """
        lines = content.strip().split('\n')
        meters = []
        current_meter = None
        interval_data = defaultdict(list)

        for line in lines:
            fields = line.strip().split(',')
            if not fields:
                continue

            record_type = fields[0]

            if record_type == '100':
                # Header record - validate version
                pass

            elif record_type == '200':
                # NMI data details
                if current_meter:
                    current_meter['interval_count'] = len(interval_data.get(current_meter['nmi'], []))
                    meters.append(current_meter)

                current_meter = self._parse_200_record(fields)
                interval_data[current_meter['nmi']] = []

            elif record_type == '300':
                # Interval data
                if current_meter:
                    intervals = self._parse_300_record(fields, current_meter)
                    interval_data[current_meter['nmi']].extend(intervals)

            elif record_type == '400':
                # Quality flags - update interval data
                pass

            elif record_type == '900':
                # End of file
                if current_meter:
                    current_meter['interval_count'] = len(interval_data.get(current_meter['nmi'], []))
                    meters.append(current_meter)

        # Store for later retrieval
        self._file_data[file_id] = {
            'meters': meters,
            'intervals': dict(interval_data),
            'processed_at': datetime.now(timezone.utc)
        }

        return meters

    def _parse_200_record(self, fields: list) -> dict:
        """Parse NMI data details record (200)."""
        return {
            'nmi': fields[1] if len(fields) > 1 else '',
            'nmi_configuration': fields[2] if len(fields) > 2 else '',
            'register_id': fields[3] if len(fields) > 3 else '',
            'nmi_suffix': fields[4] if len(fields) > 4 else '',
            'meter_serial': fields[6] if len(fields) > 6 else None,
            'unit_of_measure': fields[7] if len(fields) > 7 else 'kWh',
            'interval_length': int(fields[8]) if len(fields) > 8 and fields[8].isdigit() else 30,
            'start_date': None,
            'end_date': None,
            'total_consumption': 0.0,
            'total_generation': None
        }

    def _parse_300_record(self, fields: list, meter: dict) -> list[dict]:
        """Parse interval data record (300)."""
        interval_length = meter.get('interval_length', 30)
        intervals_per_day = 1440 // interval_length

        date_str = fields[1] if len(fields) > 1 else ''
        try:
            interval_date = datetime.strptime(date_str, '%Y%m%d').date()
        except ValueError:
            return []

        # Update meter date range
        if meter['start_date'] is None or interval_date < meter['start_date']:
            meter['start_date'] = interval_date
        if meter['end_date'] is None or interval_date > meter['end_date']:
            meter['end_date'] = interval_date

        intervals = []
        # Interval values start at index 2
        for i in range(intervals_per_day):
            idx = 2 + i
            if idx < len(fields):
                try:
                    value = float(fields[idx])
                    intervals.append({
                        'date': interval_date.isoformat(),
                        'interval': i + 1,
                        'interval_length_minutes': interval_length,
                        'value': value,
                        'unit': meter['unit_of_measure']
                    })
                    meter['total_consumption'] += value
                except ValueError:
                    pass

        return intervals

    async def get_consumption_summary(self, file_id: str) -> list[dict]:
        """Get aggregated consumption summary for a file."""
        data = self._file_data.get(file_id)
        if not data:
            # Fallback: summarize persisted retailer CSV intervals from DB.
            with SessionLocal() as db:
                rows = (
                    db.query(MeterDataInterval)
                    .filter(MeterDataInterval.file_id == file_id)
                    .order_by(MeterDataInterval.nmi.asc(), MeterDataInterval.start_at.asc())
                    .all()
                )
            if not rows:
                return []

            by_nmi: dict[str, list[MeterDataInterval]] = defaultdict(list)
            for row in rows:
                by_nmi[row.nmi].append(row)

            output: list[dict] = []
            for nmi, nmi_rows in by_nmi.items():
                total = Decimal("0")
                peak = Decimal("0")
                off_peak = Decimal("0")
                start_date = nmi_rows[0].start_at.date()
                end_date = nmi_rows[0].start_at.date()

                for item in nmi_rows:
                    value = Decimal(str(item.profile_read_value))
                    if item.rate_type_description and "solar" in item.rate_type_description.lower():
                        value = -value
                    total += value

                    local_hour = item.start_at.hour
                    is_weekday = item.start_at.weekday() < 5
                    is_peak = is_weekday and 7 <= local_hour < 22
                    if is_peak:
                        peak += value
                    else:
                        off_peak += value

                    d = item.start_at.date()
                    if d < start_date:
                        start_date = d
                    if d > end_date:
                        end_date = d

                output.append(
                    {
                        "nmi": nmi,
                        "period_start": start_date,
                        "period_end": end_date,
                        "total_kwh": float(total),
                        "peak_kwh": float(peak),
                        "off_peak_kwh": float(off_peak),
                    }
                )
            return output

        summaries = []
        for meter in data['meters']:
            intervals = data['intervals'].get(meter['nmi'], [])

            # Calculate peak/off-peak (simplified: peak = 7am-10pm weekdays)
            peak_kwh = 0.0
            off_peak_kwh = 0.0

            for interval in intervals:
                interval_date = datetime.fromisoformat(interval['date'])
                interval_num = interval['interval']
                interval_length = meter.get('interval_length', 30)

                # Calculate time from interval number
                minutes = (interval_num - 1) * interval_length
                hour = minutes // 60

                is_weekday = interval_date.weekday() < 5
                is_peak = is_weekday and 7 <= hour < 22

                if is_peak:
                    peak_kwh += interval['value']
                else:
                    off_peak_kwh += interval['value']

            summaries.append({
                'nmi': meter['nmi'],
                'period_start': meter['start_date'],
                'period_end': meter['end_date'],
                'total_kwh': meter['total_consumption'],
                'peak_kwh': peak_kwh,
                'off_peak_kwh': off_peak_kwh
            })

        return summaries

    async def get_interval_data(
        self,
        file_id: str,
        nmi: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> list[dict]:
        """Get raw interval data for charting."""
        data = self._file_data.get(file_id)
        if not data:
            with SessionLocal() as db:
                query = db.query(MeterDataInterval).filter(MeterDataInterval.file_id == file_id)
                if nmi:
                    query = query.filter(MeterDataInterval.nmi == nmi)
                rows = query.order_by(MeterDataInterval.start_at.asc()).all()

            result = []
            for item in rows:
                row_date = item.start_at.date().isoformat()
                if start_date and row_date < start_date:
                    continue
                if end_date and row_date > end_date:
                    continue
                minutes_since_midnight = item.start_at.hour * 60 + item.start_at.minute
                interval_number = (minutes_since_midnight // item.interval_length_minutes) + 1
                result.append(
                    {
                        "date": row_date,
                        "interval": interval_number,
                        "interval_length_minutes": item.interval_length_minutes,
                        "value": float(item.profile_read_value),
                        "unit": "kWh",
                        "register_code": item.register_code,
                        "rate_type_description": item.rate_type_description,
                        "quality_flag": item.quality_flag,
                        "nmi": item.nmi,
                    }
                )
            return result

        result = []
        for meter_nmi, intervals in data['intervals'].items():
            if nmi and meter_nmi != nmi:
                continue

            filtered = intervals
            if start_date:
                filtered = [i for i in filtered if i['date'] >= start_date]
            if end_date:
                filtered = [i for i in filtered if i['date'] <= end_date]

            result.extend([{**i, 'nmi': meter_nmi} for i in filtered])

        return sorted(result, key=lambda x: (x['date'], x['interval']))
