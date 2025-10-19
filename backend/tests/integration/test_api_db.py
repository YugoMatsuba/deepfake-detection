import pytest

from app import create_app
from api import get_db
from models import User


@pytest.fixture(scope="module")
def client():
    app = create_app()
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
