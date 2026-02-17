"""merge heads

Revision ID: 56b119308afc
Revises: 02aba1bc691a, a1b2c3d4e5f6
Create Date: 2026-02-17 12:35:34.431222

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '56b119308afc'
down_revision = ('02aba1bc691a', 'a1b2c3d4e5f6')
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass

