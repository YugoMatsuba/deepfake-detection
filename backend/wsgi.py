"""
WSGI entrypoint for running the Flask app under Gunicorn.

Usage examples:
  gunicorn --chdir backend wsgi:app
  gunicorn --config backend/gunicorn.conf.py --chdir backend wsgi:app
  gunicorn --bind 0.0.0.0:5050 --chdir backend 'app:create_app()'
"""

from app import create_app

# Gunicorn imports this module and uses the `app` object.
app = create_app()

