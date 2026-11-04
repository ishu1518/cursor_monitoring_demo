# Demo Linux Server Monitoring

Read-only local demo for CPU, memory, network, and listening-port usage on Linux servers.

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` on this machine only. Generate the two values:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))"
```

Put the first value in `SECRET_KEY` and the second in `ADMIN_PASSWORD_HASH`. The password stays in the hash. Do not commit `.env`.

```bash
python app.py
```

Open http://127.0.0.1:5000. The app listens on this machine only. Debug stays off unless `FLASK_DEBUG=1`.

The sign-in username is `admin`. Enter the password that matches `ADMIN_PASSWORD_HASH`. A wrong sign-in shows “Invalid username or password”. Log out from the header. After logout, pages redirect to `/login`.

## Dashboard

Monitoring data is read-only. The only write action is adding a server: display name, host, and SSH port. Records stay in the local SQLite file `monitoring.db`.

Validation rules:

- Display name is required and at most 64 characters.
- Host is a hostname or IP address.
- SSH port is an integer from 1 to 65535.
- The same host and port cannot be added twice.

Live metrics are CPU percent, memory used/total, network bytes in/out, and listening TCP ports. This computer is read directly when the host is `127.0.0.1`, `localhost`, this machine’s hostname, or one of its own addresses. Other computers are read over SSH with a fixed command. Set the SSH user on the form, or set `MONITOR_SSH_USER` in `.env`. Leave the user blank to use your SSH config. The numbers refresh every 5 seconds.

## Tests

```bash
pytest
```

`tests/test_auth.py` covers sign-in. `tests/test_servers.py` covers adding a server. `tests/test_metrics.py` stubs the collector, so the tests do not depend on live CPU values.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs `pytest` on pushes and pull requests. It does not deploy. Start the app locally to use the demo.

## Demo script

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -c "import secrets; from werkzeug.security import generate_password_hash; open('.env','w').write('SECRET_KEY='+secrets.token_hex(32)+'\nADMIN_PASSWORD_HASH='+generate_password_hash('change-me')+'\n')"
python app.py
```

Sign in at http://127.0.0.1:5000 as `admin` / `change-me`, add host `127.0.0.1`, and watch CPU, memory, network, and ports refresh.

## Files

- `app.py`
- `monitor.py`
- `requirements.txt`
- `.env.example`
- `templates/base.html`
- `templates/login.html`
- `templates/dashboard.html`
- `static/style.css`
- `static/metrics.js`
- `pytest.ini`
- `tests/test_auth.py`
- `tests/test_servers.py`
- `tests/test_metrics.py`
- `.github/workflows/ci.yml`
