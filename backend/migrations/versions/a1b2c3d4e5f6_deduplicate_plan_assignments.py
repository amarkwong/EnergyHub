"""deduplicate plan assignments and add unique constraint

Revision ID: a1b2c3d4e5f6
Revises: 0b8b8209b8e5
Create Date: 2026-02-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '0b8b8209b8e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix nulls, remove duplicates, add unique constraint."""
    # 1. Fix null network_tariff_code on the earliest rows (id 1, 2)
    op.execute(
        "UPDATE user_nmi_plan_assignments SET network_tariff_code = '31' "
        "WHERE id IN (1, 2) AND network_tariff_code IS NULL"
    )

    # 2. Delete duplicates — keep only MAX(id) per (user_nmi_id, effective_from, effective_to)
    #    SQLite does not support DELETE ... JOIN, so use a subquery.
    op.execute(
        "DELETE FROM user_nmi_plan_assignments WHERE id NOT IN ("
        "  SELECT MAX(id) FROM user_nmi_plan_assignments "
        "  GROUP BY user_nmi_id, effective_from, effective_to"
        ")"
    )

    # 3. Add unique constraint
    with op.batch_alter_table('user_nmi_plan_assignments', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_user_nmi_plan_assignment_period',
            ['user_nmi_id', 'effective_from', 'effective_to']
        )


def downgrade() -> None:
    """Drop the unique constraint (no data restore needed)."""
    with op.batch_alter_table('user_nmi_plan_assignments', schema=None) as batch_op:
        batch_op.drop_constraint('uq_user_nmi_plan_assignment_period', type_='unique')
