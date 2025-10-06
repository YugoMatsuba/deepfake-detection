"""
Flask entrypoint for Auth MVP.

Responsibilities (no business logic here):
- Load config (SECRET_KEY, DATABASE_URL).
- Initialize SQLAlchemy engine/session (via api.init_engine).
- Register blueprints (auth only for now) under /api.
- Enable CORS for /api/* in dev.
- Provide a basic /api/health endpoint.
"""

from __future__ import annotations
import os
from pathlib import Path
from flask import Flask, jsonify
from flask_cors import CORS

# DB/session utilities come from api package (to be created)
from api import init_engine, Base, engine as db_engine  # type: ignore
from api.routes.auth import bp as auth_bp, User, AuditLog  # type: ignore
from api.routes.traditional_forensics import bp_forensics

DEFAULT_DB_URL = "sqlite:///instance/app.db"

def create_app() -> Flask:
    app = Flask(__name__)

    # --- Config ---
    # TODO: set a real secret in production (.env)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-insecure")
    db_url = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

    # Ensure instance dir exists for SQLite file
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # --- DB init ---
    init_engine(db_url=db_url)
    
    # TEMP: create tables if missing (replace with Alembic later)
    Base.metadata.create_all(bind=db_engine())

    # --- CORS (dev only) ---
    # For dev Vite at http://localhost:5173. Tighten for prod.
    frontend_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173"  # default dev FE origins
    )
    origins_list = [o.strip() for o in frontend_origins.split(",") if o.strip()]
    
    CORS(
        app,
        resources={r"/api/*": {"origins": origins_list}},
        supports_credentials=True,
    )
    
    # Session cookie config for dev/prod
    is_prod = os.getenv("ENVIRONMENT") == "production"
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",   # good for top-level nav flows
        SESSION_COOKIE_SECURE=is_prod,   # flips on under HTTPS/nginx
    )

    # --- Blueprints ---
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(bp_forensics, url_prefix="/api/forensics")

    # --- Healthcheck ---
    @app.get("/api/health")
    def health():
        return jsonify(ok=True)

    return app


# For `python app.py` dev runs
if __name__ == "__main__":
    app = create_app()
    # Read PORT env if set, else default to 5050
    app.run(port=int(os.getenv("PORT", 5050)), debug=True)
