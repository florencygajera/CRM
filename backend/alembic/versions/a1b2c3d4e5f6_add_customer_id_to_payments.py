"""Add customer_id to payments table

Revision ID: a1b2c3d4e5f6
Revises: 42a25f96b645
Create Date: 2026-02-17 06:19:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '42a25f96b645'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add customer_id column with index
    op.add_column(
        'payments',
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False, index=True)
    )
    # Add composite index for tenant_id and appointment_id
    op.create_index('ix_payments_tenant_appt', 'payments', ['tenant_id', 'appointment_id'])


def downgrade() -> None:
    op.drop_index('ix_payments_tenant_appt', table_name='payments')
    op.drop_column('payments', 'customer_id')
