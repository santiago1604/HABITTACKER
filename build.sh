#!/usr/bin/env bash
# Script de build para Render
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate --noinput

# Crea el superusuario si se definieron las variables DJANGO_SUPERUSER_*
# (el plan gratuito de Render no tiene consola para hacerlo a mano)
if [[ -n "$DJANGO_SUPERUSER_USERNAME" && -n "$DJANGO_SUPERUSER_PASSWORD" ]]; then
    python manage.py createsuperuser --noinput \
        --username "$DJANGO_SUPERUSER_USERNAME" \
        --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" \
        || echo "El superusuario ya existe; se omite."
fi
