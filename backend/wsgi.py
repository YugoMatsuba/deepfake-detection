"""
WSGI entrypoint for running the Flask app under Gunicorn.

Usage examples:
  gunicorn --chdir backend wsgi:app
  gunicorn --config backend/gunicorn.conf.py --chdir backend wsgi:app
  gunicorn --bind 0.0.0.0:5050 --chdir backend 'app:create_app()'
"""

import os
from app import create_app

# Gunicorn imports this module and uses the `app` object.
app = create_app()

# Log database configuration on startup
db_url = os.getenv("DATABASE_URL", "NOT_SET")
print(f"[WSGI] Database: PostgreSQL ({db_url})", flush=True)
