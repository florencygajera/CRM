"""add branch_id to appoitments and payments

Revision ID: 6ac0909ec73d
Revises: 56b119308afc
Create Date: 2026-02-17 12:36:48.345107

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '6ac0909ec73d'
down_revision = '56b119308afc'
branch_labels = None
depends_on = None

def upgrade():
    # 1) add nullable columns first
    op.add_column("appointments", sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("payments", sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True))

    # 2) backfill
    op.execute("""
        UPDATE appointments a
        SET branch_id = b.id
        FROM branches b
        WHERE a.tenant_id = b.tenant_id
          AND b.id = (
            SELECT id FROM branches b2
            WHERE b2.tenant_id = a.tenant_id
            ORDER BY b2.id ASC
            LIMIT 1
          )
          AND a.branch_id IS NULL;
    """)

    op.execute("""
        UPDATE payments p
        SET branch_id = a.branch_id
        FROM appointments a
        WHERE p.appointment_id = a.id
          AND p.branch_id IS NULL;
    """)

    op.execute("""
        UPDATE payments p
        SET branch_id = b.id
        FROM branches b
        WHERE p.tenant_id = b.tenant_id
          AND b.id = (
            SELECT id FROM branches b2
            WHERE b2.tenant_id = p.tenant_id
            ORDER BY b2.id ASC
            LIMIT 1
          )
          AND p.branch_id IS NULL;
    """)

    # 3) enforce NOT NULL
    op.alter_column("appointments", "branch_id", nullable=False)
    op.alter_column("payments", "branch_id", nullable=False)

    # 4) add foreign keys
    op.create_foreign_key(
        "fk_appointments_branch_id",
        "appointments",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_payments_branch_id",
        "payments",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 5) indexes
    op.create_index("ix_appointments_tenant_branch", "appointments", ["tenant_id", "branch_id"])
    op.create_index("ix_payments_tenant_branch", "payments", ["tenant_id", "branch_id"])


def downgrade():
    op.drop_index("ix_payments_tenant_branch", table_name="payments")
    op.drop_index("ix_appointments_tenant_branch", table_name="appointments")

    op.drop_constraint("fk_payments_branch_id", "payments", type_="foreignkey")
    op.drop_constraint("fk_appointments_branch_id", "appointments", type_="foreignkey")

    op.drop_column("payments", "branch_id")
    op.drop_column("appointments", "branch_id")
