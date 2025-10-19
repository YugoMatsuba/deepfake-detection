import importlib
import os
import sys
import types
from contextlib import ExitStack
from unittest.mock import patch

import pytest

from api import get_db
from models import User


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("DB_BOOTSTRAP", "1")

    with ExitStack() as stack:
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

        if "database" not in sys.modules:
            database_stub = types.ModuleType("database")
            database_stub.get_db = lambda *args, **kwargs: None
            sys.modules["database"] = database_stub
            stack.callback(lambda: sys.modules.pop("database", None))

        app_module = importlib.import_module("app")
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
