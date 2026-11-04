from tests.conftest import FAKE_METRICS, csrf_token


def test_anonymous_metrics_request_redirects_to_login(client):
    response = client.get("/api/servers/1/metrics")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_fake_collector_returns_fixed_keys(auth_client):
    added = auth_client.post(
        "/servers",
        data={
            "csrf_token": csrf_token(auth_client),
            "name": "this-machine",
            "host": "127.0.0.1",
            "ssh_port": "22",
        },
    )
    assert added.status_code == 302
    response = auth_client.get("/api/servers/1/metrics?extra=ignore-me")
    assert response.status_code == 200
    body = response.get_json()
    assert body == {
        "collected": True,
        "cpu_percent": FAKE_METRICS["cpu_percent"],
        "memory_used": FAKE_METRICS["memory_used"],
        "memory_total": FAKE_METRICS["memory_total"],
        "bytes_sent": FAKE_METRICS["bytes_sent"],
        "bytes_recv": FAKE_METRICS["bytes_recv"],
        "ports": FAKE_METRICS["ports"],
    }
    assert "extra" not in body


def test_this_machine_addresses_are_local():
    import socket

    import psutil

    from app import is_local_host

    seen = False
    for addresses in psutil.net_if_addrs().values():
        for address in addresses:
            if address.family == socket.AF_INET and address.address:
                assert is_local_host(address.address) is True
                seen = True
    assert seen is True
    assert is_local_host("203.0.113.10") is False


def test_remote_server_uses_the_supplied_collector(tmp_path, monkeypatch):
    from werkzeug.security import generate_password_hash

    from app import create_app
    from tests.conftest import FAKE_METRICS, csrf_token

    def remote(host, port, user):
        assert host == "10.9.8.7"
        assert port == 22
        assert user == "ubuntu"
        return dict(FAKE_METRICS)

    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", generate_password_hash("test-password"))
    monkeypatch.setenv("MONITORING_DB", str(tmp_path / "remote.db"))
    application = create_app(
        collector=lambda: dict(FAKE_METRICS),
        remote_collector=remote,
    )
    application.config["TESTING"] = True
    client = application.test_client()
    assert (
        client.post(
            "/login",
            data={"username": "admin", "password": "test-password"},
        ).status_code
        == 302
    )
    added = client.post(
        "/servers",
        data={
            "csrf_token": csrf_token(client),
            "name": "remote",
            "host": "10.9.8.7",
            "ssh_port": "22",
            "ssh_user": "ubuntu",
        },
    )
    assert added.status_code == 302
    body = client.get("/api/servers/1/metrics").get_json()
    assert body["collected"] is True
    assert body["cpu_percent"] == FAKE_METRICS["cpu_percent"]


def test_other_hosts_are_not_collected(auth_client):
    auth_client.post(
        "/servers",
        data={
            "csrf_token": csrf_token(auth_client),
            "name": "remote",
            "host": "10.9.8.7",
            "ssh_port": "22",
        },
    )
    response = auth_client.get("/api/servers/1/metrics")
    assert response.get_json()["collected"] is False
    assert response.get_json()["ports"] == []
