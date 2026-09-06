# backend/alembic/versions/005_add_postgis_extensions.py

"""Add PostGIS extensions

Revision ID: 005
Revises: 004
Create Date: 2026-09-04 10:04:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Enable PostGIS extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")
    
    # Convert existing geom column from text to geometry if data exists
    try:
        op.execute("ALTER TABLE cameras ALTER COLUMN geom TYPE geometry(Point,4326) USING ST_GeomFromText(geom, 4326)")
    except Exception:
        # If conversion fails, just drop and recreate the column
        op.execute("ALTER TABLE cameras DROP COLUMN IF EXISTS geom")
        op.execute("ALTER TABLE cameras ADD COLUMN geom geometry(Point,4326)")
    
    # Create spatial index
    op.execute("CREATE INDEX IF NOT EXISTS ix_cameras_geom ON cameras USING GIST (geom)")


def downgrade():
    # Remove geometry column and index
    op.execute("DROP INDEX IF EXISTS ix_cameras_geom")
    op.execute("ALTER TABLE cameras DROP COLUMN IF EXISTS geom")
    
    # Re-add text column for compatibility with previous migration
    op.execute("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS geom text")
    
    # Disable PostGIS extensions
    op.execute("DROP EXTENSION IF EXISTS postgis_topology")
    op.execute("DROP EXTENSION IF EXISTS postgis")
