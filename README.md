# HabitTracker

Aplicación Django para seguir hábitos diarios y gestionar tareas.

## Funciones

- **Dashboard**: hábitos de la semana con casillas para marcarlos, rachas, tareas próximas y estadísticas rápidas.
- **Hábitos**: crear, editar, reordenar arrastrando, archivar/restaurar y ver el historial de 12 semanas con rachas.
- **Tareas**: prioridades, fecha límite, avisos de tareas vencidas o para hoy, búsqueda y filtros, reordenar arrastrando y limpiar las completadas.
- **Calendario** (menú "Calendario", con un selector para pasar de una vista a otra):
  - **Día**: marcar los hábitos de cualquier día pasado, ver las tareas con fecha ese día, las vencidas (si es hoy) y las completadas ese día.
  - **Semana**: agenda de tareas y seguimiento de hábitos.
  - **Mes**: calendario con el cumplimiento de hábitos por día (mapa de calor), tareas por día, días perfectos y resumen por hábito.
  - **Año**: 12 minicalendarios con mapa de calor, mejor mes, días activos y resumen anual por hábito; se puede filtrar por un hábito.
- **Informe de progreso**: gráfico acumulado por hábito o de cumplimiento diario, con rangos rápidos.
- **Exportar** hábitos y tareas a CSV (menú de usuario).
- Tema claro/oscuro.

## Puesta en marcha local

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env            # opcional: ajusta las variables
python manage.py migrate
python manage.py createsuperuser  # opcional
python manage.py runserver
```

Tests: `python manage.py test tracker`

## Despliegue en Render

El repositorio incluye `render.yaml` (Blueprint) y `build.sh`. En Render: **New → Blueprint**, elige el repositorio y se crearán el servicio web y la base de datos PostgreSQL con todas las variables configuradas. Opcionalmente, rellena `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD` y `DJANGO_SUPERUSER_EMAIL` para crear un administrador durante el build.

Variables de entorno:

| Variable | Descripción |
|---|---|
| `DJANGO_DEBUG` | `False` en producción |
| `DJANGO_SECRET_KEY` | Obligatoria si `DEBUG` es `False` |
| `DJANGO_ALLOWED_HOSTS` | Hosts separados por comas (Render añade `RENDER_EXTERNAL_HOSTNAME` automáticamente) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Orígenes con esquema, p. ej. `https://midominio.com` |
| `DATABASE_URL` | Opcional, p. ej. PostgreSQL. Por defecto se usa SQLite |
| `DJANGO_HSTS_SECONDS` | Opcional, activa HSTS |

Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
Start: `gunicorn habittracker.wsgi`
