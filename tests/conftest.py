import pytest
from werkzeug.security import generate_password_hash

from app import create_app

PASSWORD = "test-password"
FAKE_METRICS = {
    "cpu_percent": 12.5,
    "memory_used": 1000,
    "memory_total": 2000,
    "bytes_sent": 10,
    "bytes_recv": 20,
    "ports": [22, 80],
}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv(
        "ADMIN_PASSWORD_HASH", generate_password_hash(PASSWORD)
    )
    monkeypatch.setenv("MONITORING_DB", str(tmp_path / "monitoring.db"))
    application = create_app(
        collector=lambda: dict(FAKE_METRICS),
        remote_collector=lambda host, port, user: None,
    )
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    response = client.post(
        "/login",
        data={"username": "admin", "password": PASSWORD},
    )
    assert response.status_code == 302
    return client


def csrf_token(client):
    with client.session_transaction() as sess:
        return sess["csrf_token"]
