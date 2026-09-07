#!/bin/bash
set -e

echo "Starting TrackX Backend..."

# Check if using SQLite or PostgreSQL
if [ "$USE_SQLITE" = "true" ] || [ -z "$DATABASE_URL" ]; then
    echo "Using SQLite database"
    # Ensure SQLite database directory exists
    mkdir -p /app/outputs/results
    touch /app/outputs/results/observations.db || true
else
    echo "Using PostgreSQL database"
    # Wait for PostgreSQL to be ready
    echo "Waiting for database to be ready..."
    sleep 15
    
    # Test database connection
    if ! PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_SERVER" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q' 2>/dev/null; then
        echo "Warning: Could not connect to PostgreSQL, but continuing..."
    fi
fi

# Try to run migrations (may fail for SQLite, that's okay)
echo "Running database migrations..."
if alembic upgrade head 2>/dev/null; then
  echo "Migrations completed successfully"
else
  echo "Migration skipped or failed (non-critical), continuing..."
fi

# Start the application
echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
