# backend/alembic/versions/004_create_alerts.py

"""Create alerts table

Revision ID: 004
Revises: 003
Create Date: 2026-09-04 10:03:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('alert_id', sa.String(length=50), unique=True, index=True),
        sa.Column('alert_type', sa.String(length=50), index=True),
        sa.Column('severity', sa.String(length=20), index=True),
        sa.Column('plate_text', sa.String(length=30), index=True),
        sa.Column('normalized_plate', sa.String(length=30), index=True),
        sa.Column('vehicle_type', sa.String(length=30)),
        sa.Column('camera_id', sa.String(length=20)),
        sa.Column('timestamp', sa.DateTime(), index=True),
        sa.Column('evidence_json', sa.JSON()),
        sa.Column('description', sa.String(length=1000)),
        sa.Column('confidence', sa.Float()),
        sa.Column('similarity', sa.Float()),
        sa.Column('status', sa.String(length=20), server_default='OPEN', index=True),
        sa.Column('resolved_by', sa.String(length=100)),
        sa.Column('resolved_at', sa.DateTime()),
        sa.Column('resolution_notes', sa.String(length=1000)),
        sa.Column('metadata', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )


def downgrade():
    op.drop_table('alerts')
