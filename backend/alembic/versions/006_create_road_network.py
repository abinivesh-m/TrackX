"""Create road_network table

Revision ID: 006
Revises: 005
Create Date: 2026-09-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'road_network',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('camera_a', sa.String(), nullable=False),
        sa.Column('camera_b', sa.String(), nullable=False),
        sa.Column('distance_km', sa.Float(), nullable=False),
        sa.Column('speed_limit_kmph', sa.Integer(), nullable=False),
        sa.Column('road_type', sa.String(), nullable=True),
        sa.Column('traffic_condition', sa.String(), nullable=True),
        sa.Column('lanes', sa.Integer(), nullable=True),
        sa.Column('has_traffic_lights', sa.Boolean(), nullable=True),
        sa.Column('typical_travel_time_min', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('camera_a', 'camera_b', name='uq_road_connection')
    )
    op.create_index(op.f('ix_road_network_camera_a'), 'road_network', ['camera_a'], unique=False)
    op.create_index(op.f('ix_road_network_camera_b'), 'road_network', ['camera_b'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_road_network_camera_b'), table_name='road_network')
    op.drop_index(op.f('ix_road_network_camera_a'), table_name='road_network')
    op.drop_table('road_network')
