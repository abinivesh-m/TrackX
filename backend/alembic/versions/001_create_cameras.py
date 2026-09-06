# backend/alembic/versions/001_create_cameras.py

"""Create cameras table

Revision ID: 001
Revises: 
Create Date: 2026-09-04 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create cameras table
    op.create_table(
        'cameras',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('camera_id', sa.String(length=20), unique=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('location', sa.String(length=200)),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),

        sa.Column('direction', sa.String(length=50)),
        sa.Column('road', sa.String(length=100)),
        sa.Column('camera_type', sa.String(length=50), server_default='CCTV'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('last_seen', sa.DateTime()),
        sa.Column('metadata', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    
    # Add geometry column as text initially (will be converted to geometry in migration 005)
    op.add_column('cameras', sa.Column('geom', sa.String()))
    
    # Create index
    op.create_index('ix_cameras_camera_id', 'cameras', ['camera_id'])


def downgrade():
    op.drop_index('ix_cameras_camera_id', 'cameras')
    op.drop_column('cameras', 'geom')
    op.drop_table('cameras')
