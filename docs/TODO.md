# TODO — Demo Linux Server Monitoring

Local Flask demo for internal L1, L2, and L3 teams. Read-only view of CPU, memory, network, and listening ports. Sign in as `admin` with a hashed password. Add Linux servers from the UI. Run it on this machine only.

Do one checkbox at a time, in order. Each step includes a security note and a documentation note. Leave deploy as a local process; CI only runs tests.

## 1. Project initialization and basic UI

- [x] **1.1** Add `requirements.txt` with pinned `Flask`, plus `.gitignore` for `.env`, `venv/`, `__pycache__/`, and `*.db`.
  - [x] Security: pin versions and keep secrets and local data out of git.
  - [x] Docs: start `README.md` with a one-line description of the demo.
- [x] **1.2** Add `app.py` that creates a Flask app and returns a plain “Monitoring” page.
  - [x] Security: bind to `127.0.0.1` and a local port (default `5000`). Leave debug off unless `FLASK_DEBUG=1`.
  - [x] Docs: README section “Run locally” with venv, `pip install -r requirements.txt`, and `python app.py`.
- [x] **1.3** Add `templates/base.html` and a short `static/style.css` (header, card layout, readable type).
  - [x] Security: serve only project static files. Do not render user HTML.
  - [x] Docs: name the CSS file in the README file list.
- [x] **1.4** Add `templates/dashboard.html`: empty server list and placeholder cards for CPU, memory, network, and ports. No buttons that change a server.
  - [x] Security: page is view-only. No forms yet.
  - [x] Docs: state in the README that the dashboard is read-only.

## 2. Sign-in and unit tests

- [x] **2.1** Add `.env.example` with `SECRET_KEY` and `ADMIN_PASSWORD_HASH`. Load them in the app. Username is fixed: `admin`.
  - [x] Security: hash with Werkzeug (`generate_password_hash` / `check_password_hash`). Never commit a real `.env` or a plaintext password.
  - [x] Docs: README steps to copy `.env.example`, generate a hash, and fill in local values.
- [x] **2.2** Add `GET/POST /login` and `templates/login.html` (username, password, submit).
  - [x] Security: one generic error (“Invalid username or password”). Do not log the password.
  - [x] Docs: document the default username `admin` and that the password lives only in the local env hash.
- [x] **2.3** On success, store `user=admin` in a session. Send unauthenticated visits to `/` and other app pages to `/login`. Add `POST /logout`.
  - [x] Security: `HttpOnly` and `SameSite=Lax` session cookie. Secret key comes from the environment.
  - [x] Docs: describe the login and logout flow in the README.
- [x] **2.4** Add `tests/test_auth.py` with `pytest` (wrong password rejected, right password sets the session, logged-out user is redirected). Pin `pytest` in `requirements.txt`.
  - [x] Security: tests must not print secrets; use a hash created inside the test.
  - [x] Docs: README section “Tests” with `pytest`.

## 3. Add a Linux server

- [x] **3.1** Add SQLite file `monitoring.db` (gitignored) and a `servers` table: `id`, `name`, `host`, `ssh_port` (default 22).
  - [x] Security: the app creates the file itself with a fixed schema. No raw SQL built from request strings.
  - [x] Docs: note that server records stay in the local SQLite file.
- [x] **3.2** Add `POST /servers` and a small form on the dashboard: display name, host, SSH port.
  - [x] Security: require a signed-in admin. Add a CSRF token in the session and the form.
  - [x] Docs: document the three fields and that this is the only write action in the UI.
- [x] **3.3** Validate input: name length, host as a hostname or IP, SSH port 1–65535. Reject duplicates. Show errors on the form.
  - [x] Security: store the host as data. Do not pass it to a shell.
  - [x] Docs: list the validation rules in the README.
- [x] **3.4** List saved servers on the dashboard. Each row is text only (name, host, port).
  - [x] Security: escape all values in templates (default Jinja escaping).
  - [x] Docs: add a “Add a server” subsection to the README.
- [x] **3.5** Add `tests/test_servers.py`: rejected bad host, saved valid server, list visible only after login.
  - [x] Security: cover CSRF failure (POST without token is rejected).
  - [x] Docs: mention the new test module next to the `pytest` command.

## 4. Read-only live metrics

- [x] **4.1** Add `monitor.py` with one function that reads this machine via `psutil`: CPU percent, memory used/total, bytes sent/received, and listening TCP ports. Pin `psutil`.
  - [x] Security: read local system counters only. No shell calls.
  - [x] Docs: list the four metrics in the README.
- [x] **4.2** Show those numbers on the dashboard for a server whose host is this machine (`127.0.0.1` or the local hostname). Other hosts show “Not collected”.
  - [x] Security: metrics endpoints require a signed-in session. Responses are JSON or HTML from server-side values only.
  - [x] Docs: explain that this demo collects live data for the local machine first.
- [x] **4.3** Refresh the metric cards every 5 seconds from `GET /api/servers/<id>/metrics`.
  - [x] Security: JSON response has fixed keys. Ignore any extra query parameters.
  - [x] Docs: note the 5-second refresh.
- [x] **4.4** Add `tests/test_metrics.py` using a fake collector (no dependency on live CPU values).
  - [x] Security: assert an anonymous request to the metrics URL is redirected to login.
  - [x] Docs: note that tests stub the collector.

## 5. CI/CD with GitHub Actions

- [x] **5.1** Add `.github/workflows/ci.yml` on `push` and `pull_request`: checkout, Python 3.12, install `requirements.txt`, run `pytest`.
  - [x] Security: `permissions: contents: read`. No secrets and no deploy step.
  - [x] Docs: README “CI” section — GitHub Actions runs tests; start the app locally to use the demo.
- [x] **5.2** Confirm the workflow command matches the local test command.
  - [x] Security: CI uses the same pinned dependencies as the app.
  - [x] Docs: add the workflow path to the README file list.

## 6. Local demo check

- [x] **6.1** From a clean venv: install, set `.env`, start the app, sign in as `admin`, add this machine as a server, and see CPU, memory, network, and ports update.
  - [x] Security: confirm the browser talks only to `127.0.0.1`, logout works, and `.env` is untracked.
  - [x] Docs: add a five-line “Demo script” to the README with that path.
