"""Invoice reconciliation engine."""
import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from app.schemas.reconciliation import DiscrepancyStatus
from app.services.invoice_parser import InvoiceParser
from app.services.invoice_calculator import InvoiceCalculator


class ReconciliationEngine:
    """
    Engine for reconciling parsed invoices against calculated values.

    Compares line-by-line and identifies discrepancies.
    """

    def __init__(self):
        self._invoice_parser = InvoiceParser()
        self._invoice_calculator = InvoiceCalculator()

        # Storage for reconciliation results
        self._reconciliations = {}

    async def reconcile(
        self,
        invoice_file_id: str,
        nem12_file_id: str,
        network_tariff_code: Optional[str] = None,
        retail_plan_name: Optional[str] = None,
        tolerance_percent: float = 1.0
    ) -> dict:
        """
        Run reconciliation between parsed invoice and calculated values.

        Args:
            invoice_file_id: ID of parsed invoice
            nem12_file_id: ID of NEM12 consumption data
            network_tariff_code: Tariff code to use for calculation
            retail_plan_name: Retail plan name (optional)
            tolerance_percent: Acceptable discrepancy threshold

        Returns:
            Reconciliation summary with line-by-line breakdown
        """
        # Get parsed invoice
        parsed = await self._invoice_parser.get_invoice(invoice_file_id)
        if not parsed:
            raise ValueError("Parsed invoice not found")

        # Calculate expected invoice
        calculated = await self._invoice_calculator.calculate(
            nem12_file_id=nem12_file_id,
            network_tariff_code=network_tariff_code or 'EA010',
            retail_plan_name=retail_plan_name,
            billing_start=parsed.get('billing_period_start', '').isoformat() if parsed.get('billing_period_start') else None,
            billing_end=parsed.get('billing_period_end', '').isoformat() if parsed.get('billing_period_end') else None
        )

        # Reconcile line items
        line_reconciliations = self._reconcile_line_items(
            parsed.get('line_items', []),
            calculated.get('line_items', []),
            tolerance_percent
        )

        # Calculate totals
        invoiced_total = Decimal(str(parsed.get('total', 0)))
        calculated_total = Decimal(str(calculated.get('total', 0)))
        total_difference = invoiced_total - calculated_total

        if calculated_total > 0:
            total_percentage = float(abs(total_difference) / calculated_total * 100)
        else:
            total_percentage = 100.0 if total_difference != 0 else 0.0

        # Count discrepancy types
        matched = sum(1 for r in line_reconciliations if r['status'] == 'match')
        minor = sum(1 for r in line_reconciliations if r['status'] == 'minor')
        significant = sum(1 for r in line_reconciliations if r['status'] == 'significant')
        missing = sum(1 for r in line_reconciliations if r['status'] in ['missing_invoiced', 'missing_calculated'])

        # Determine overall status
        if significant > 0 or abs(total_percentage) > 5:
            overall_status = 'significant'
        elif minor > 0 or missing > 0 or abs(total_percentage) > tolerance_percent:
            overall_status = 'minor'
        else:
            overall_status = 'match'

        # Calculate confidence based on matching
        total_items = len(line_reconciliations)
        confidence = matched / total_items if total_items > 0 else 0.0

        # Generate recommendations
        recommendations = self._generate_recommendations(
            line_reconciliations,
            total_difference,
            total_percentage
        )

        reconciliation_id = str(uuid.uuid4())

        result = {
            'reconciliation_id': reconciliation_id,
            'nmi': parsed.get('nmi', calculated.get('nmi', 'Unknown')),
            'invoice_number': parsed.get('invoice_number', 'Unknown'),
            'billing_period_start': parsed.get('billing_period_start'),
            'billing_period_end': parsed.get('billing_period_end'),
            'invoiced_total': invoiced_total,
            'calculated_total': calculated_total,
            'total_difference': total_difference,
            'total_percentage_difference': round(total_percentage, 2),
            'line_items': line_reconciliations,
            'matched_items': matched,
            'minor_discrepancies': minor,
            'significant_discrepancies': significant,
            'missing_items': missing,
            'overall_status': overall_status,
            'confidence_score': round(confidence, 2),
            'recommendations': recommendations
        }

        # Store for later retrieval
        self._reconciliations[reconciliation_id] = result

        return result

    def _reconcile_line_items(
        self,
        invoiced_items: list,
        calculated_items: list,
        tolerance_percent: float
    ) -> list[dict]:
        """Reconcile individual line items."""
        reconciled = []

        # Create lookup by charge type
        calc_by_type = {}
        for item in calculated_items:
            charge_type = item.get('charge_type', 'other')
            if charge_type not in calc_by_type:
                calc_by_type[charge_type] = []
            calc_by_type[charge_type].append(item)

        invoiced_matched = set()
        calculated_matched = set()

        # Match invoiced items to calculated
        for i, inv_item in enumerate(invoiced_items):
            charge_type = inv_item.get('charge_type', 'other')
            inv_amount = Decimal(str(inv_item.get('amount', 0)))

            best_match = None
            best_diff = None

            # Find best matching calculated item
            for j, calc_item in enumerate(calc_by_type.get(charge_type, [])):
                if j in calculated_matched:
                    continue

                calc_amount = Decimal(str(calc_item.get('amount', 0)))
                diff = inv_amount - calc_amount

                if best_diff is None or abs(diff) < abs(best_diff):
                    best_match = (j, calc_item)
                    best_diff = diff

            if best_match:
                j, calc_item = best_match
                calculated_matched.add(j)
                invoiced_matched.add(i)

                calc_amount = Decimal(str(calc_item.get('amount', 0)))
                diff = inv_amount - calc_amount

                if calc_amount > 0:
                    pct_diff = float(abs(diff) / calc_amount * 100)
                else:
                    pct_diff = 100.0 if diff != 0 else 0.0

                # Determine status
                if pct_diff <= tolerance_percent:
                    status = 'match'
                elif pct_diff <= 5:
                    status = 'minor'
                else:
                    status = 'significant'

                reconciled.append({
                    'description': inv_item.get('description', ''),
                    'charge_type': charge_type,
                    'invoiced_quantity': inv_item.get('quantity'),
                    'invoiced_rate': inv_item.get('rate'),
                    'invoiced_amount': inv_amount,
                    'calculated_quantity': calc_item.get('quantity'),
                    'calculated_rate': calc_item.get('rate'),
                    'calculated_amount': calc_amount,
                    'amount_difference': diff,
                    'percentage_difference': round(pct_diff, 2),
                    'status': status,
                    'notes': self._get_discrepancy_note(status, diff, pct_diff)
                })
            else:
                # No matching calculated item
                reconciled.append({
                    'description': inv_item.get('description', ''),
                    'charge_type': charge_type,
                    'invoiced_quantity': inv_item.get('quantity'),
                    'invoiced_rate': inv_item.get('rate'),
                    'invoiced_amount': inv_amount,
                    'calculated_quantity': None,
                    'calculated_rate': None,
                    'calculated_amount': Decimal('0'),
                    'amount_difference': inv_amount,
                    'percentage_difference': None,
                    'status': 'missing_calculated',
                    'notes': 'Item on invoice but not in calculated values'
                })

        # Add any calculated items without matching invoiced items
        for charge_type, items in calc_by_type.items():
            for j, calc_item in enumerate(items):
                if j not in calculated_matched:
                    calc_amount = Decimal(str(calc_item.get('amount', 0)))
                    reconciled.append({
                        'description': calc_item.get('description', ''),
                        'charge_type': charge_type,
                        'invoiced_quantity': None,
                        'invoiced_rate': None,
                        'invoiced_amount': Decimal('0'),
                        'calculated_quantity': calc_item.get('quantity'),
                        'calculated_rate': calc_item.get('rate'),
                        'calculated_amount': calc_amount,
                        'amount_difference': -calc_amount,
                        'percentage_difference': None,
                        'status': 'missing_invoiced',
                        'notes': 'Calculated item not found on invoice'
                    })

        return reconciled

    def _get_discrepancy_note(
        self,
        status: str,
        diff: Decimal,
        pct_diff: float
    ) -> Optional[str]:
        """Generate a note explaining the discrepancy."""
        if status == 'match':
            return None

        if diff > 0:
            direction = "Invoiced amount is higher"
        else:
            direction = "Invoiced amount is lower"

        return f"{direction} by ${abs(diff):.2f} ({pct_diff:.1f}%)"

    def _generate_recommendations(
        self,
        reconciliations: list,
        total_diff: Decimal,
        total_pct: float
    ) -> list[str]:
        """Generate recommendations based on reconciliation results."""
        recommendations = []

        # Check for significant total difference
        if abs(total_pct) > 5:
            if total_diff > 0:
                recommendations.append(
                    f"Total invoiced amount is ${total_diff:.2f} ({total_pct:.1f}%) higher than calculated. "
                    "Consider contacting retailer to verify charges."
                )
            else:
                recommendations.append(
                    f"Total invoiced amount is ${abs(total_diff):.2f} ({total_pct:.1f}%) lower than calculated. "
                    "Verify tariff rates used in calculation."
                )

        # Check for missing items
        missing_inv = [r for r in reconciliations if r['status'] == 'missing_invoiced']
        missing_calc = [r for r in reconciliations if r['status'] == 'missing_calculated']

        if missing_calc:
            recommendations.append(
                f"{len(missing_calc)} invoice line item(s) could not be matched to calculated values. "
                "Review tariff configuration."
            )

        if missing_inv:
            recommendations.append(
                f"{len(missing_inv)} calculated charge(s) not found on invoice. "
                "May indicate missing charges or different tariff structure."
            )

        # Check for usage discrepancies
        usage_items = [r for r in reconciliations
                       if r['charge_type'] == 'usage' and r['status'] == 'significant']
        if usage_items:
            recommendations.append(
                "Significant discrepancy in usage charges. "
                "Verify meter readings and NEM12 data covers the billing period."
            )

        if not recommendations:
            recommendations.append("Invoice appears to match calculated values within tolerance.")

        return recommendations

    async def get_reconciliation(self, reconciliation_id: str) -> Optional[dict]:
        """Get a stored reconciliation result."""
        return self._reconciliations.get(reconciliation_id)

    async def get_history(self, nmi: str, limit: int = 10) -> list[dict]:
        """Get reconciliation history for an NMI."""
        history = [
            {
                'reconciliation_id': r['reconciliation_id'],
                'nmi': r['nmi'],
                'invoice_number': r['invoice_number'],
                'billing_period_start': r['billing_period_start'],
                'billing_period_end': r['billing_period_end'],
                'overall_status': r['overall_status'],
                'total_difference': r['total_difference'],
                'reconciled_at': date.today()
            }
            for r in self._reconciliations.values()
            if r.get('nmi') == nmi
        ]
        return history[:limit]

    async def export(self, reconciliation_id: str, format: str) -> Optional[dict]:
        """Export reconciliation results."""
        result = self._reconciliations.get(reconciliation_id)
        if not result:
            return None

        if format == 'csv':
            # Generate CSV content
            lines = ['Description,Charge Type,Invoiced Amount,Calculated Amount,Difference,Status']
            for item in result['line_items']:
                lines.append(
                    f"{item['description']},{item['charge_type']},"
                    f"{item['invoiced_amount']},{item['calculated_amount']},"
                    f"{item['amount_difference']},{item['status']}"
                )
            return {
                'content': '\n'.join(lines),
                'content_type': 'text/csv',
                'filename': f"reconciliation_{reconciliation_id}.csv"
            }

        # PDF export would require additional library
        return {'error': 'PDF export not yet implemented'}
