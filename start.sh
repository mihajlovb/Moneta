#!/usr/bin/env bash
# Render start step. The free plan has an ephemeral disk, so the SQLite database
# is recreated and the demo account (demo / demo1234) is re-seeded on every start.
set -o errexit
python manage.py migrate --noinput
python manage.py seed_demo
# Optional admin account: set DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD in Render.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py createsuperuser --noinput --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" || true
fi
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000}
