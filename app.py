import ipaddress
import os
import re
import secrets
import socket
import sqlite3

import psutil
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from monitor import CollectionError, collect_local_metrics, collect_remote_metrics

HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
SSH_USER = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,31}$")
NAME_MAX = 64


def load_dotenv(path=".env"):
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if key:
                os.environ.setdefault(key, value)


def create_app(collector=None, remote_collector=None):
    missing = [
        name
        for name in ("SECRET_KEY", "ADMIN_PASSWORD_HASH")
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError("Missing environment values: " + ", ".join(missing))

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    app.config["ADMIN_PASSWORD_HASH"] = os.environ["ADMIN_PASSWORD_HASH"]
    app.config["DATABASE"] = os.environ.get("MONITORING_DB", "monitoring.db")
    app.config["COLLECTOR"] = collector or collect_local_metrics
    app.config["REMOTE_COLLECTOR"] = remote_collector or collect_remote_metrics
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    init_db(app.config["DATABASE"])

    @app.context_processor
    def inject_auth():
        return {
            "logged_in": session.get("user") == "admin",
            "csrf_token": session.get("csrf_token", ""),
        }

    @app.before_request
    def require_login():
        if request.endpoint in {"login", "static"}:
            return None
        if session.get("user") != "admin":
            return redirect(url_for("login"))
        return None

    @app.get("/")
    def dashboard():
        servers = list_servers()
        return render_template(
            "dashboard.html",
            servers=servers,
            errors=[],
            form_name="",
            form_host="",
            form_port="22",
            form_user="",
            **metrics_context(servers),
        )

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            try:
                password_ok = check_password_hash(
                    app.config["ADMIN_PASSWORD_HASH"], password
                )
            except (TypeError, ValueError):
                password_ok = False
            if username != "admin" or not password_ok:
                error = "Invalid username or password"
            else:
                session.clear()
                session["user"] = "admin"
                session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect(url_for("dashboard"))
        return render_template("login.html", error=error)

    @app.post("/logout")
    def logout():
        if not csrf_ok():
            return redirect(url_for("dashboard"))
        session.clear()
        return redirect(url_for("login"))

    @app.post("/servers")
    def add_server():
        servers = list_servers()
        form_name = request.form.get("name", "")
        form_host = request.form.get("host", "")
        form_port = request.form.get("ssh_port", "")
        form_user = request.form.get("ssh_user", "")
        if not csrf_ok():
            return (
                render_dashboard(
                    servers,
                    ["The form expired. Refresh the page and try again."],
                    form_name,
                    form_host,
                    form_port or "22",
                    form_user,
                ),
                400,
            )
        errors, name, host, port, user = validate_server(
            form_name, form_host, form_port, form_user
        )
        if errors:
            return (
                render_dashboard(
                    servers, errors, form_name, form_host, form_port or "22", form_user
                ),
                400,
            )
        try:
            insert_server(name, host, port, user)
        except sqlite3.IntegrityError:
            if user:
                update_ssh_user(host, port, user)
                return redirect(url_for("dashboard"))
            errors = ["That server is already listed."]
            return (
                render_dashboard(
                    servers, errors, form_name, form_host, str(port), form_user
                ),
                400,
            )
        return redirect(url_for("dashboard"))

    @app.get("/api/servers/<int:server_id>/metrics")
    def server_metrics(server_id):
        server = find_server(server_id)
        if server is None:
            return jsonify({"error": "Not found"}), 404
        if not server["local"]:
            return jsonify(remote_payload(server))
        return jsonify(collected_payload())

    return app


def init_db(path):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                host TEXT NOT NULL,
                ssh_port INTEGER NOT NULL DEFAULT 22
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS servers_host_port
            ON servers (host, ssh_port)
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(servers)")}
        if "ssh_user" not in columns:
            conn.execute(
                "ALTER TABLE servers ADD COLUMN ssh_user TEXT NOT NULL DEFAULT ''"
            )
        conn.commit()
    finally:
        conn.close()


def connect():
    from flask import current_app

    conn = sqlite3.connect(current_app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def list_servers():
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT id, name, host, ssh_port, ssh_user FROM servers ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    return [server_view(row) for row in rows]


def find_server(server_id):
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id, name, host, ssh_port, ssh_user FROM servers WHERE id = ?",
            (server_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return server_view(row)


def insert_server(name, host, port, user):
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO servers (name, host, ssh_port, ssh_user) VALUES (?, ?, ?, ?)",
            (name, host, port, user),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_ssh_user(host, port, user):
    conn = connect()
    try:
        conn.execute(
            "UPDATE servers SET ssh_user = ? WHERE host = ? AND ssh_port = ?",
            (user, host, port),
        )
        conn.commit()
    finally:
        conn.close()


def server_view(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "host": row["host"],
        "ssh_port": row["ssh_port"],
        "ssh_user": row["ssh_user"] or "",
        "local": is_local_host(row["host"]),
    }


def validate_server(name, host, port_raw, user_raw=""):
    errors = []
    name = (name or "").strip()
    host_input = (host or "").strip()
    user = (user_raw or "").strip()
    if not name or len(name) > NAME_MAX:
        errors.append("Enter a display name up to 64 characters.")
    normalized = normalize_host(host_input)
    if normalized is None:
        errors.append("Enter a hostname or IP address.")
    port = parse_port(port_raw)
    if port is None:
        errors.append("Enter a port from 1 to 65535.")
    if user and SSH_USER.fullmatch(user) is None:
        errors.append("Enter an SSH user such as ubuntu, or leave it blank.")
    if not errors:
        for server in list_servers():
            if server["host"] == normalized and server["ssh_port"] == port and not user:
                errors.append("That server is already listed.")
                break
    return errors, name, normalized, port, user


def parse_port(port_raw):
    try:
        port = int(str(port_raw).strip())
    except (TypeError, ValueError):
        return None
    if 1 <= port <= 65535:
        return port
    return None


def normalize_host(host):
    if not host or len(host) > 253 or any(char.isspace() for char in host):
        return None
    try:
        return ipaddress.ip_address(host).compressed
    except ValueError:
        pass
    trimmed = host[:-1] if host.endswith(".") else host
    labels = trimmed.split(".")
    if not labels or any(HOST_LABEL.fullmatch(label) is None for label in labels):
        return None
    return trimmed.lower()


def is_local_host(host):
    normalized = normalize_host(host)
    if normalized is None:
        return False
    return normalized in local_names()


def local_names():
    names = {"127.0.0.1", "::1", "localhost"}
    hostname = socket.gethostname().strip().lower().rstrip(".")
    if hostname:
        names.add(hostname)
    fqdn = socket.getfqdn().strip().lower().rstrip(".")
    if fqdn:
        names.add(fqdn)
    try:
        interfaces = psutil.net_if_addrs().values()
    except Exception:
        interfaces = []
    for addresses in interfaces:
        for address in addresses:
            if address.family not in (socket.AF_INET, socket.AF_INET6):
                continue
            ip_text = (address.address or "").split("%", 1)[0]
            try:
                names.add(ipaddress.ip_address(ip_text).compressed)
            except ValueError:
                continue
    return names


def csrf_ok():
    token = session.get("csrf_token", "")
    sent = request.form.get("csrf_token", "")
    if not token or not sent or len(token) != len(sent):
        return False
    return secrets.compare_digest(token, sent)


def collected_payload():
    from flask import current_app

    try:
        raw = current_app.config["COLLECTOR"]()
    except Exception:
        current_app.logger.exception("metrics collection failed")
        return not_collected()
    return public_metrics(raw)


def remote_payload(server):
    from flask import current_app

    user = (server.get("ssh_user") or os.environ.get("MONITOR_SSH_USER") or "").strip()
    if user and SSH_USER.fullmatch(user) is None:
        return not_collected("SSH user is invalid")
    try:
        raw = current_app.config["REMOTE_COLLECTOR"](
            server["host"], int(server["ssh_port"]), user
        )
    except CollectionError as exc:
        return not_collected(exc.detail)
    except Exception:
        current_app.logger.exception("remote metrics failed")
        return not_collected("SSH failed")
    if not raw:
        return not_collected()
    return public_metrics(raw)


def public_metrics(raw):
    return {
        "collected": True,
        "cpu_percent": raw["cpu_percent"],
        "memory_used": raw["memory_used"],
        "memory_total": raw["memory_total"],
        "bytes_sent": raw["bytes_sent"],
        "bytes_recv": raw["bytes_recv"],
        "ports": list(raw["ports"]),
    }


def not_collected(detail="Not collected"):
    return {
        "collected": False,
        "cpu_percent": None,
        "memory_used": None,
        "memory_total": None,
        "bytes_sent": None,
        "bytes_recv": None,
        "ports": [],
        "detail": detail,
    }


def metric_text(payload):
    if not payload["collected"]:
        return ("Not collected",) * 4
    cpu = f"{payload['cpu_percent']:.0f}%"
    memory = (
        f"{format_bytes(payload['memory_used'])} / "
        f"{format_bytes(payload['memory_total'])}"
    )
    network = (
        f"{format_bytes(payload['bytes_recv'])} in · "
        f"{format_bytes(payload['bytes_sent'])} out"
    )
    ports = ", ".join(str(port) for port in payload["ports"]) or "None"
    return cpu, memory, network, ports


def format_bytes(size):
    amount = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(amount)} B"
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TB"


def metrics_context(servers):
    local = next((server for server in servers if server["local"]), None)
    if local is None:
        cpu, memory, network, ports = ("Not collected",) * 4 if servers else ("—",) * 4
        return {
            "cpu": cpu,
            "memory": memory,
            "network": network,
            "ports": ports,
            "metrics_url": None,
            "card_title": "This computer",
        }
    cpu, memory, network, ports = metric_text(collected_payload())
    return {
        "cpu": cpu,
        "memory": memory,
        "network": network,
        "ports": ports,
        "metrics_url": url_for("server_metrics", server_id=local["id"]),
        "card_title": local["name"],
    }


def render_dashboard(servers, errors, form_name, form_host, form_port, form_user=""):
    return render_template(
        "dashboard.html",
        servers=servers,
        errors=errors,
        form_name=form_name,
        form_host=form_host,
        form_port=form_port,
        form_user=form_user,
        **metrics_context(servers),
    )


if __name__ == "__main__":
    load_dotenv()
    application = create_app()
    debug = os.environ.get("FLASK_DEBUG") == "1"
    application.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "5000")),
        debug=debug,
    )
