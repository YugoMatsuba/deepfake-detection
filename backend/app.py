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
from flask_compress import Compress

# DB/session utilities come from api package
from api import init_engine, Base, engine as db_engine, get_db, hash_password  # type: ignore
from api.routes.auth import bp as auth_bp  # type: ignore
from api.routes.video_upload import video_bp
from api.routes.analysis import analysis_bp
from api.routes.admin import admin_bp  # Admin dashboard routes
from api.routes.reports import reports_bp  # PDF report generation
# Models now in consolidated models.py (managed by Alembic)
from models import User
from dotenv import load_dotenv

load_dotenv()

DEFAULT_DB_URL = "postgresql+psycopg://deepfake:secret@localhost:5431/deepfake_dev"


def bootstrap_owner_from_env():
    """
    Ensure exactly one owner exists, based on OWNER_USERNAME env var.
    Called once at app startup, before any requests.

    Hardened behavior:
    - If OWNER_USERNAME not set: skip (no owner enforcement)
    - If no owners exist: create/promote env user to owner
    - If owner(s) already exist: only transfer if ALLOW_OWNER_TRANSFER=1

    Environment variables:
    - OWNER_USERNAME: Required username for the owner
    - OWNER_SEED_PASSWORD: Password for creating owner (only needed on first boot)
    - ALLOW_OWNER_TRANSFER: Set to "1" to allow changing owner (default "0")

    Security:
    - Only promotes to owner if no owners exist OR explicitly allowed via env var
    - Prevents accidental owner takeover
    """
    owner_username = os.getenv("OWNER_USERNAME")
    if not owner_username:
        # Only warn if user is trying to bootstrap (ALLOW_OWNER_TRANSFER=1) but forgot username
        if os.getenv("ALLOW_OWNER_TRANSFER", "0") == "1":
            print("⚠ ALLOW_OWNER_TRANSFER=1 but no OWNER_USERNAME set - cannot bootstrap")
        # Otherwise silently skip (normal operation when owner already exists)
        return

    with get_db() as db:
        # Count existing owners
        owner_count = db.query(User).filter(
            User.role == "owner",
            User.active.is_(True)
        ).count()

        # Find env user
        user = db.query(User).filter(User.username == owner_username).first()

        # Only create/promote if no owners exist
        if owner_count == 0:
            if not user:
                # Create new owner
                seed_pw = os.getenv("OWNER_SEED_PASSWORD")
                if not seed_pw:
                    raise RuntimeError(
                        f"OWNER_USERNAME={owner_username} set but user doesn't exist "
                        "and OWNER_SEED_PASSWORD not provided."
                    )
                user = User(
                    username=owner_username,
                    password_hash=hash_password(seed_pw),
                    role="owner",
                    active=True,
                    pending_approval=False,
                )
                db.add(user)
                db.commit()
                print(f"✓ Created owner user: {owner_username}")
            else:
                # Promote existing user to owner and reset password if provided
                seed_pw = os.getenv("OWNER_SEED_PASSWORD")
                if seed_pw:
                    user.password_hash = hash_password(seed_pw)
                user.role = "owner"
                user.active = True
                user.pending_approval = False
                db.commit()
                print(f"✓ Promoted {owner_username} to owner (no existing owners)")
                if seed_pw:
                    print("  Password reset to OWNER_SEED_PASSWORD")

        elif owner_count >= 1:
            # Owner already exists - only transfer if explicitly allowed
            allow_transfer = os.getenv("ALLOW_OWNER_TRANSFER", "0") == "1"
            if not allow_transfer:
                print("⚠ Owner already exists. ALLOW_OWNER_TRANSFER not set. Skipping bootstrap.")
                return

            # Transfer ownership: demote current owners and promote env user
            current_owners = db.query(User).filter(
                User.role == "owner",
                User.active.is_(True)
            ).all()

            for o in current_owners:
                if o.username != owner_username:
                    o.role = "admin"
                    print(f"✓ Demoted {o.username} from owner to admin")

            if user:
                # Transfer ownership and reset password to env value
                seed_pw = os.getenv("OWNER_SEED_PASSWORD")
                if seed_pw:
                    user.password_hash = hash_password(seed_pw)
                user.role = "owner"
                user.active = True
                user.pending_approval = False
                db.commit()
                print(f"✓ Transferred ownership to {owner_username}")
                if seed_pw:
                    print("  Password reset to OWNER_SEED_PASSWORD")
            else:
                raise RuntimeError(
                    f"OWNER_USERNAME={owner_username} doesn't exist and an owner already exists. "
                    "Cannot transfer ownership to non-existent user."
                )


def create_app() -> Flask:
    app = Flask(__name__)

    # --- Config ---
    # TODO: set a real secret in production (.env)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-insecure")
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500MB max upload
    db_url = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

    # Ensure instance dir exists for SQLite file (only when using SQLite)
    if db_url.startswith("sqlite"):
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # --- DB init ---
    init_engine(db_url=db_url)

    # Tables now managed by Alembic migrations (run: alembic upgrade head)
    # For local dev bootstrap only, set DB_BOOTSTRAP=1 to auto-create tables
    if os.getenv("DB_BOOTSTRAP", "0") == "1":
        Base.metadata.create_all(bind=db_engine())

    # --- Owner Bootstrap ---
    # Enforce single owner from env vars (after DB init, before serving requests)
    bootstrap_owner_from_env()

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

    # --- Compression (gzip) ---
    Compress(app)

    # --- Blueprints ---
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(video_bp, url_prefix="/api")
    app.register_blueprint(analysis_bp, url_prefix="/api")
    app.register_blueprint(reports_bp, url_prefix="/api")

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
