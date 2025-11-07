import importlib
import sys
import types
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

from api import get_db
from models import User


@pytest.fixture(scope="function")
def client():
    # Changed to function scope to work with _schema fixture from conftest.py

    with ExitStack() as stack:
        backend_dir = Path(__file__).resolve().parents[2]
        backend_path = str(backend_dir)
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
            stack.callback(lambda: sys.path.remove(backend_path))

        cleanup_module = None
        try:
            cleanup_module = importlib.import_module("cleanup_scheduler")
        except ModuleNotFoundError:
            cleanup_module = types.ModuleType("cleanup_scheduler")
            cleanup_module.init_scheduler = lambda *args, **kwargs: None
            cleanup_module.cleanup_job = lambda *args, **kwargs: None
            sys.modules["cleanup_scheduler"] = cleanup_module
            stack.callback(lambda: sys.modules.pop("cleanup_scheduler", None))
        else:
            stack.enter_context(
                patch.object(cleanup_module, "init_scheduler", return_value=None)
            )
            if hasattr(cleanup_module, "cleanup_job"):
                stack.enter_context(
                    patch.object(cleanup_module, "cleanup_job", return_value=None)
                )

        try:
            importlib.import_module("database")
        except ModuleNotFoundError:
            database_stub = types.ModuleType("database")
            database_stub.get_db = lambda *args, **kwargs: None
            sys.modules["database"] = database_stub
            stack.callback(lambda: sys.modules.pop("database", None))

        app_module = importlib.import_module("app")
        stack.enter_context(
            patch.object(app_module, "bootstrap_owner_from_env", return_value=None)
        )
        app = app_module.create_app()
        app.config.update(TESTING=True)

        with app.test_client() as test_client:
            yield test_client


def test_register_persists_user(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "integration_admin", "password": "secret-pass"},
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["username"] == "integration_admin"
    assert payload["role"] == "admin"

    with get_db() as db:
        stored_user = db.query(User).filter(User.username == "integration_admin").one()
        assert stored_user.role == "admin"
        assert stored_user.active is True


def test_login_reads_user_from_db(client):
    register_resp = client.post(
        "/api/auth/register",
        json={"username": "integration_user", "password": "secret-pass"},
    )
    assert register_resp.status_code == 201

    response = client.post(
        "/api/auth/login",
        json={"username": "integration_user", "password": "secret-pass"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["user"]["username"] == "integration_user"
    assert payload["user"]["role"] == "admin"
