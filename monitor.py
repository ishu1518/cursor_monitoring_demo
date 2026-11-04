import json
import subprocess

import psutil

REMOTE_SCRIPT = """
import json, time
def snap():
    parts = open("/proc/stat").readline().split()[1:]
    nums = list(map(int, parts))
    return sum(nums), nums[3] + nums[4]
total_a, idle_a = snap()
time.sleep(0.1)
total_b, idle_b = snap()
delta = total_b - total_a
cpu = 0 if delta <= 0 else round((1 - (idle_b - idle_a) / delta) * 100, 1)
mem = {}
for line in open("/proc/meminfo"):
    key, value = line.split(":", 1)
    mem[key] = int(value.split()[0]) * 1024
rx = tx = 0
for line in open("/proc/net/dev"):
    if ":" not in line:
        continue
    cols = line.split(":", 1)[1].split()
    rx += int(cols[0])
    tx += int(cols[8])
ports = []
for name in ("/proc/net/tcp", "/proc/net/tcp6"):
    try:
        rows = open(name).read().splitlines()[1:]
    except FileNotFoundError:
        continue
    for row in rows:
        cols = row.split()
        if len(cols) > 3 and cols[3] == "0A":
            ports.append(int(cols[1].rsplit(":", 1)[1], 16))
used = mem.get("MemTotal", 0) - mem.get("MemAvailable", mem.get("MemFree", 0))
print(json.dumps({
    "cpu_percent": cpu,
    "memory_used": used,
    "memory_total": mem.get("MemTotal", 0),
    "bytes_sent": tx,
    "bytes_recv": rx,
    "ports": sorted(set(ports)),
}))
""".strip()


class CollectionError(Exception):
    def __init__(self, detail):
        super().__init__(detail)
        self.detail = detail


def collect_local_metrics():
    """Read CPU, memory, network, and listening TCP ports on this machine."""
    memory = psutil.virtual_memory()
    network = psutil.net_io_counters()
    ports = []
    try:
        connections = psutil.net_connections(kind="tcp")
    except (psutil.AccessDenied, PermissionError):
        connections = []
    for connection in connections:
        if connection.status == psutil.CONN_LISTEN and connection.laddr:
            ports.append(connection.laddr.port)
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_used": memory.used,
        "memory_total": memory.total,
        "bytes_sent": network.bytes_sent,
        "bytes_recv": network.bytes_recv,
        "ports": sorted(set(ports)),
    }


def collect_remote_metrics(host, port, user):
    """Read the same counters from a Linux host over SSH. The command is fixed."""
    destination = f"{user}@{host}" if user else host
    try:
        completed = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-p",
                str(int(port)),
                destination,
                "python3 -c " + "'" + REMOTE_SCRIPT + "'",
            ],
            capture_output=True,
            timeout=12,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CollectionError("Host unreachable") from exc
    if completed.returncode != 0:
        raise CollectionError(ssh_failure_detail(completed.stderr))
    try:
        return parse_remote_metrics(completed.stdout)
    except (ValueError, KeyError, TypeError) as exc:
        raise CollectionError("SSH failed") from exc


def parse_remote_metrics(stdout):
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", "replace")
    data = json.loads(stdout)
    return {
        "cpu_percent": float(data["cpu_percent"]),
        "memory_used": int(data["memory_used"]),
        "memory_total": int(data["memory_total"]),
        "bytes_sent": int(data["bytes_sent"]),
        "bytes_recv": int(data["bytes_recv"]),
        "ports": sorted(int(port) for port in data["ports"]),
    }


def ssh_failure_detail(stderr):
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", "replace")
    text = stderr.lower()
    if "permission denied" in text or "authentication" in text:
        return "SSH login failed"
    if (
        "timed out" in text
        or "connection refused" in text
        or "no route" in text
        or "could not resolve" in text
    ):
        return "Host unreachable"
    return "SSH failed"
