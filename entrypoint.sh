#!/bin/bash
set -e

echo "Entrypoint Started..."
echo "ENABLE_MAKEMIGRATIONS=$ENABLE_MAKEMIGRATIONS"
echo "ENABLE_MIGRATE_SHARED=$ENABLE_MIGRATE_SHARED"
echo "ENABLE_COLLECTSTATIC=$ENABLE_COLLECTSTATIC"

if [ "$ENABLE_MAKEMIGRATIONS" = "true" ]; then
    echo "Running makemigrations..."
    poetry run python manage.py makemigrations
else
    echo "Skipping makemigrations..."
fi

if [ "$ENABLE_MIGRATE_SHARED" = "true" ]; then
    echo "Running migrate_schemas --shared..."
    poetry run python manage.py migrate_schemas --shared
else
    echo "Skipping migrate_schemas --shared..."
fi

if [ "$ENABLE_COLLECTSTATIC" = "true" ]; then
    echo "Running collectstatic..."
    poetry run python manage.py collectstatic --noinput
else
    echo "Skipping collectstatic..."
fi

echo "Starting Gunicorn..."
exec poetry run gunicorn config.wsgi:application --bind 0.0.0.0:8000
