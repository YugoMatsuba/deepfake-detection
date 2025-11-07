"""
Gunicorn configuration for the Deepfake Detection backend.

Environment variables (override defaults):
  PORT                  -> bind port (default 5050)
  WEB_CONCURRENCY       -> number of worker processes
  GUNICORN_THREADS      -> threads per worker (default 2)
  GUNICORN_TIMEOUT      -> worker timeout seconds (default 120)
  GUNICORN_KEEPALIVE    -> keepalive seconds (default 5)
  GUNICORN_LOGLEVEL     -> log level (default 'info')
"""

import multiprocessing
import os


def _default_workers() -> int:
    try:
        cpu = multiprocessing.cpu_count()
    except NotImplementedError:
        cpu = 2
    # Reasonable default: half the CPUs, at least 1
    return max(1, cpu // 2)


bind = f"0.0.0.0:{os.getenv('PORT', '5050')}"
workers = int(os.getenv("WEB_CONCURRENCY", _default_workers()))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Logging to stdout/stderr so container platforms can capture logs
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")

# Flask is sync and mostly IO bound here; gthread gives concurrency per worker
worker_class = "gthread"

# Trust proxy headers when running behind reverse proxy
forwarded_allow_ips = "*"
secure_scheme_headers = {"X-Forwarded-Proto": "https"}
