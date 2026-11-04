import json

from monitor import REMOTE_SCRIPT, collect_remote_metrics, parse_remote_metrics


def test_remote_ssh_command_keeps_the_host_out_of_the_script(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args

        class Result:
            returncode = 0
            stdout = json.dumps(
                {
                    "cpu_percent": 1,
                    "memory_used": 2,
                    "memory_total": 3,
                    "bytes_sent": 4,
                    "bytes_recv": 5,
                    "ports": [22],
                }
            ).encode()
            stderr = b""

        return Result()

    monkeypatch.setattr("monitor.subprocess.run", fake_run)
    result = collect_remote_metrics("10.1.2.3", 2222, "ubuntu")
    args = captured["args"]
    assert args[0] == "ssh"
    assert "ubuntu@10.1.2.3" in args
    assert "2222" in args
    assert args[-1].startswith("python3 -c ")
    assert "10.1.2.3" not in args[-1]
    assert "ubuntu" not in args[-1]
    assert result["ports"] == [22]


def test_remote_script_can_parse_local_counters():
    import subprocess

    completed = subprocess.run(
        ["python3", "-c", REMOTE_SCRIPT],
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert completed.returncode == 0
    data = parse_remote_metrics(completed.stdout)
    assert data["memory_total"] > 0
    assert isinstance(data["ports"], list)
