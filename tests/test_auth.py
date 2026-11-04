import pytest
from werkzeug.security import generate_password_hash

from app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    password_hash = generate_password_hash("test-password")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", password_hash)
    monkeypatch.setenv("MONITORING_DB", str(tmp_path / "auth.db"))
    application = create_app()
    application.config["TESTING"] = True
    return application.test_client()


def test_session_cookie_is_http_only_and_lax(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv(
        "ADMIN_PASSWORD_HASH", generate_password_hash("test-password")
    )
    monkeypatch.setenv("MONITORING_DB", str(tmp_path / "cookie.db"))
    application = create_app()
    assert application.config["SESSION_COOKIE_HTTPONLY"] is True
    assert application.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert application.config["SECRET_KEY"] == "test-secret-key"


def test_wrong_password_is_rejected(client):
    response = client.post(
        "/login",
        data={"username": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 200
    assert b"Invalid username or password" in response.data
    assert b"wrong-password" not in response.data
    with client.session_transaction() as sess:
        assert "user" not in sess


def test_right_password_sets_the_session(client):
    response = client.post(
        "/login",
        data={"username": "admin", "password": "test-password"},
    )
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess["user"] == "admin"


def test_logged_out_user_is_redirected(client):
    client.post(
        "/login",
        data={"username": "admin", "password": "test-password"},
    )
    with client.session_transaction() as sess:
        token = sess["csrf_token"]
    response = client.post("/logout", data={"csrf_token": token})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    page = client.get("/")
    assert page.status_code == 302
    assert page.headers["Location"].endswith("/login")
