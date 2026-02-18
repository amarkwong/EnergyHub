"""create invoice tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-17 10:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create invoices, invoice_line_items, and reconciliation_results tables."""
    op.create_table(
        'invoices',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('file_id', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('nmi', sa.String(16), nullable=True),
        sa.Column('retailer', sa.String(128), nullable=True),
        sa.Column('energy_plan_name', sa.String(256), nullable=True),
        sa.Column('network_provider', sa.String(128), nullable=True),
        sa.Column('invoice_number', sa.String(64), nullable=True),
        sa.Column('invoice_date', sa.String(16), nullable=True),
        sa.Column('due_date', sa.String(16), nullable=True),
        sa.Column('billing_period_start', sa.String(16), nullable=True),
        sa.Column('billing_period_end', sa.String(16), nullable=True),
        sa.Column('service_address', sa.String(512), nullable=True),
        sa.Column('service_state', sa.String(8), nullable=True),
        sa.Column('service_postcode', sa.String(8), nullable=True),
        sa.Column('subtotal', sa.Numeric(12, 2), nullable=True),
        sa.Column('gst', sa.Numeric(12, 2), nullable=True),
        sa.Column('total', sa.Numeric(12, 2), nullable=True),
        sa.Column('amount_due', sa.Numeric(12, 2), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('warnings_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'invoice_line_items',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('description', sa.String(512), nullable=True),
        sa.Column('charge_type', sa.String(64), nullable=True),
        sa.Column('quantity', sa.Numeric(16, 6), nullable=True),
        sa.Column('unit', sa.String(16), nullable=True),
        sa.Column('rate', sa.Numeric(12, 4), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('tariff_code', sa.String(64), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
    )

    op.create_table(
        'reconciliation_results',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('reconciliation_id', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('invoices.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('nem12_file_id', sa.String(64), nullable=True),
        sa.Column('network_tariff_code', sa.String(64), nullable=True),
        sa.Column('retail_plan_name', sa.String(256), nullable=True),
        sa.Column('overall_status', sa.String(32), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('invoiced_total', sa.Numeric(12, 2), nullable=True),
        sa.Column('calculated_total', sa.Numeric(12, 2), nullable=True),
        sa.Column('total_difference', sa.Numeric(12, 2), nullable=True),
        sa.Column('recommendations_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Drop invoice-related tables."""
    op.drop_table('reconciliation_results')
    op.drop_table('invoice_line_items')
    op.drop_table('invoices')
