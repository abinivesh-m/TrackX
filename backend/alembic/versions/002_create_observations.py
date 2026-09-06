# backend/alembic/versions/002_create_observations.py

"""Create observations table

Revision ID: 002
Revises: 001
Create Date: 2026-09-04 10:01:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Create observations table
    op.create_table(
        'observations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plate_text', sa.String(length=30), index=True),
        sa.Column('normalized_plate', sa.String(length=30), index=True),
        sa.Column('raw_plate_text', sa.String(length=30)),
        sa.Column('ocr_confidence', sa.Float()),
        sa.Column('plate_status', sa.String(length=30), server_default='detected'),
        sa.Column('vehicle_type', sa.String(length=30)),
        sa.Column('vehicle_color', sa.String(length=30)),
        sa.Column('vehicle_make', sa.String(length=50)),
        sa.Column('vehicle_model', sa.String(length=50)),
        sa.Column('appearance_vector', sa.JSON()),
        sa.Column('camera_id', sa.String(length=20), sa.ForeignKey('cameras.camera_id'), index=True),
        sa.Column('timestamp', sa.DateTime(), index=True),
        sa.Column('confidence', sa.Float()),
        sa.Column('vehicle_bbox', sa.JSON()),
        sa.Column('vehicle_confidence', sa.Float()),
        sa.Column('plate_bbox', sa.JSON()),
        sa.Column('plate_confidence', sa.Float()),
        sa.Column('source_file', sa.String(length=500)),
        sa.Column('source_type', sa.String(length=20)),
        sa.Column('frame_index', sa.Integer()),
        sa.Column('data_source', sa.String(length=30), server_default='REAL_INFERENCE'),
        sa.Column('track_id', sa.String(length=50), index=True),
        sa.Column('global_id', sa.Integer(), index=True),
        sa.Column('match_score', sa.Float()),
        sa.Column('match_breakdown', sa.JSON()),
        sa.Column('annotated_output', sa.String(length=500)),
        sa.Column('plate_crop_path', sa.String(length=500)),
        sa.Column('evidence_thumbnail', sa.String(length=500)),
        sa.Column('metadata', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )


def downgrade():
    op.drop_table('observations')
