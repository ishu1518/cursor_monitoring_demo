from tests.conftest import PASSWORD, csrf_token


def test_bad_host_is_rejected(auth_client):
    response = auth_client.post(
        "/servers",
        data={
            "csrf_token": csrf_token(auth_client),
            "name": "bad",
            "host": "bad host; rm -rf",
            "ssh_port": "22",
        },
    )
    assert response.status_code == 400
    assert b"hostname or IP" in response.data
    page = auth_client.get("/")
    assert b"bad host" not in page.data


def test_valid_server_is_saved_and_escaped(auth_client):
    response = auth_client.post(
        "/servers",
        data={
            "csrf_token": csrf_token(auth_client),
            "name": "<b>web</b>",
            "host": "10.1.2.3",
            "ssh_port": "2222",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"&lt;b&gt;web&lt;/b&gt;" in response.data
    assert b"10.1.2.3" in response.data
    assert b"2222" in response.data
    assert b"Checking" in response.data


def test_duplicate_server_is_rejected(auth_client):
    payload = {
        "csrf_token": csrf_token(auth_client),
        "name": "edge",
        "host": "10.1.2.3",
        "ssh_port": "22",
    }
    assert auth_client.post("/servers", data=payload).status_code == 302
    payload["csrf_token"] = csrf_token(auth_client)
    response = auth_client.post("/servers", data=payload)
    assert response.status_code == 400
    assert b"already listed" in response.data


def test_server_list_is_visible_only_after_login(auth_client):
    auth_client.post(
        "/servers",
        data={
            "csrf_token": csrf_token(auth_client),
            "name": "edge",
            "host": "10.1.2.3",
            "ssh_port": "22",
        },
    )
    with auth_client.session_transaction() as sess:
        token = sess["csrf_token"]
    auth_client.post("/logout", data={"csrf_token": token})
    hidden = auth_client.get("/")
    assert hidden.status_code == 302
    assert hidden.headers["Location"].endswith("/login")
    assert b"10.1.2.3" not in hidden.data
    login = auth_client.post(
        "/login",
        data={"username": "admin", "password": PASSWORD},
        follow_redirects=True,
    )
    assert b"10.1.2.3" in login.data


def test_post_without_csrf_token_is_rejected(auth_client):
    response = auth_client.post(
        "/servers",
        data={"name": "edge", "host": "10.1.2.3", "ssh_port": "22"},
    )
    assert response.status_code == 400
    assert b"form expired" in response.data
    page = auth_client.get("/")
    assert b"10.1.2.3" not in page.data
