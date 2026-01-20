"""Invoice calculation service."""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from app.services.nem12_service import NEM12Service
from app.services.tariff_fetcher import TariffFetcher


class InvoiceCalculator:
    """Service for calculating expected invoice from consumption and tariffs."""

    def __init__(self):
        self._nem12_service = NEM12Service()
        self._tariff_fetcher = TariffFetcher()

    async def calculate(
        self,
        nem12_file_id: str,
        network_tariff_code: str,
        retail_plan_name: Optional[str] = None,
        billing_start: str = None,
        billing_end: str = None
    ) -> dict:
        """
        Calculate expected invoice based on consumption and tariffs.

        Args:
            nem12_file_id: ID of uploaded NEM12 file
            network_tariff_code: Network tariff code to apply
            retail_plan_name: Optional retail plan name
            billing_start: Billing period start (YYYY-MM-DD)
            billing_end: Billing period end (YYYY-MM-DD)

        Returns:
            Calculated invoice with line items
        """
        # Get consumption data
        summaries = await self._nem12_service.get_consumption_summary(nem12_file_id)
        if not summaries:
            raise ValueError("No consumption data found for file ID")

        summary = summaries[0]  # Use first NMI for now

        # Get tariff details
        network_tariff = await self._tariff_fetcher.get_tariff_by_code(
            provider=None,  # Will be determined from tariff code
            tariff_code=network_tariff_code
        )

        # Determine billing period
        if billing_start and billing_end:
            period_start = datetime.strptime(billing_start, '%Y-%m-%d').date()
            period_end = datetime.strptime(billing_end, '%Y-%m-%d').date()
        else:
            period_start = summary['period_start']
            period_end = summary['period_end']

        billing_days = (period_end - period_start).days + 1

        line_items = []

        # Calculate supply charge
        if network_tariff:
            daily_supply = Decimal(str(network_tariff.get('daily_supply_charge_cents', 100))) / 100
            supply_amount = (daily_supply * billing_days).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            line_items.append({
                'description': 'Daily Supply Charge',
                'charge_type': 'supply',
                'quantity': float(billing_days),
                'unit': 'day',
                'rate': daily_supply,
                'amount': supply_amount,
                'tariff_code': network_tariff_code,
                'period_start': period_start,
                'period_end': period_end
            })

        # Calculate usage charges
        total_kwh = Decimal(str(summary['total_kwh']))
        peak_kwh = Decimal(str(summary['peak_kwh']))
        off_peak_kwh = Decimal(str(summary['off_peak_kwh']))

        # Check if TOU or flat rate
        if network_tariff and network_tariff.get('time_periods'):
            # TOU tariff - calculate peak and off-peak separately
            peak_rate = self._get_period_rate(network_tariff, 'peak')
            off_peak_rate = self._get_period_rate(network_tariff, 'off_peak')

            if peak_kwh > 0:
                peak_amount = (peak_kwh * peak_rate / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                line_items.append({
                    'description': 'Peak Energy Usage',
                    'charge_type': 'usage',
                    'quantity': float(peak_kwh),
                    'unit': 'kWh',
                    'rate': peak_rate / 100,  # Convert to $/kWh
                    'amount': peak_amount,
                    'tariff_code': network_tariff_code
                })

            if off_peak_kwh > 0:
                off_peak_amount = (off_peak_kwh * off_peak_rate / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                line_items.append({
                    'description': 'Off-Peak Energy Usage',
                    'charge_type': 'usage',
                    'quantity': float(off_peak_kwh),
                    'unit': 'kWh',
                    'rate': off_peak_rate / 100,
                    'amount': off_peak_amount,
                    'tariff_code': network_tariff_code
                })
        else:
            # Flat rate tariff
            flat_rate = Decimal(str(network_tariff.get('usage_rate_cents_per_kwh', 25))) if network_tariff else Decimal('25')
            usage_amount = (total_kwh * flat_rate / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            line_items.append({
                'description': 'Energy Usage',
                'charge_type': 'usage',
                'quantity': float(total_kwh),
                'unit': 'kWh',
                'rate': flat_rate / 100,
                'amount': usage_amount,
                'tariff_code': network_tariff_code
            })

        # Calculate network charges (simplified - usually part of retail price)
        network_rate = Decimal('0.08')  # $/kWh - typical network component
        network_amount = (total_kwh * network_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        line_items.append({
            'description': 'Network Charges',
            'charge_type': 'network',
            'quantity': float(total_kwh),
            'unit': 'kWh',
            'rate': network_rate,
            'amount': network_amount
        })

        # Calculate totals
        subtotal = sum(item['amount'] for item in line_items)
        gst = (subtotal * Decimal('0.10')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total = subtotal + gst

        return {
            'nmi': summary['nmi'],
            'billing_period_start': period_start,
            'billing_period_end': period_end,
            'line_items': line_items,
            'subtotal': subtotal,
            'gst': gst,
            'total': total,
            'calculation_notes': f'Calculated using tariff {network_tariff_code}'
        }

    def _get_period_rate(self, tariff: dict, period_name: str) -> Decimal:
        """Get rate for a specific TOU period."""
        for period in tariff.get('time_periods', []):
            if period.get('name', '').lower() == period_name.lower():
                return Decimal(str(period.get('rate_cents_per_kwh', 25)))

        # Default rates if not found
        defaults = {'peak': 35, 'off_peak': 18, 'shoulder': 25}
        return Decimal(str(defaults.get(period_name, 25)))
