#!/bin/bash
set -e

echo "Starting TrackX Backend..."

# Wait a bit for database to be ready (Render handles service dependencies)
echo "Waiting for database to be ready..."
sleep 10

# Try to run migrations
echo "Running database migrations..."
if alembic upgrade head; then
  echo "Migrations completed successfully"
else
  echo "Migration failed, but continuing..."
fi

# Start the application
echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
