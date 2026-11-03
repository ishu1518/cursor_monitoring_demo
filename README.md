# Demo Linux Server Monitoring

Read-only local demo for CPU, memory, network, and listening-port usage on Linux servers.

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The app listens on this machine only. Debug stays off unless `FLASK_DEBUG=1`.

## Dashboard

The dashboard is read-only. It shows the server list and placeholder cards for CPU, memory, network, and ports. It has no actions that change a server.

## Files

- `app.py`
- `requirements.txt`
- `templates/base.html`
- `templates/dashboard.html`
- `static/style.css`
