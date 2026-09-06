# backend/alembic/versions/003_create_vehicles.py

"""Create vehicles table

Revision ID: 003
Revises: 002
Create Date: 2026-09-04 10:02:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Create vehicles table
    op.create_table(
        'vehicles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plate_number', sa.String(length=30), unique=True, index=True, nullable=False),
        sa.Column('normalized_plate', sa.String(length=30), unique=True, index=True, nullable=False),
        sa.Column('state_code', sa.String(length=2)),
        sa.Column('rto_code', sa.Integer()),
        sa.Column('vehicle_type', sa.String(length=30)),
        sa.Column('vehicle_make', sa.String(length=50)),
        sa.Column('vehicle_model', sa.String(length=50)),
        sa.Column('vehicle_color', sa.String(length=30)),
        sa.Column('fuel_type', sa.String(length=20)),
        sa.Column('registration_status', sa.String(length=20), server_default='VALID'),
        sa.Column('watchlist_status', sa.String(length=20), server_default='CLEAR'),
        sa.Column('watchlist_reason', sa.String(length=500)),
        sa.Column('owner_name', sa.String(length=100)),
        sa.Column('owner_address', sa.String(length=500)),
        sa.Column('owner_phone', sa.String(length=20)),
        sa.Column('insurance_expiry', sa.DateTime()),
        sa.Column('puc_expiry', sa.DateTime()),
        sa.Column('fitness_expiry', sa.DateTime()),
        sa.Column('typical_appearance', sa.JSON()),
        sa.Column('data_source', sa.String(length=30), server_default='MANUAL'),
        sa.Column('source_agency', sa.String(length=100)),
        sa.Column('first_seen', sa.DateTime()),
        sa.Column('last_seen', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('metadata', sa.JSON()),
    )


def downgrade():
    op.drop_table('vehicles')
