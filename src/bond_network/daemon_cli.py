import ctypes
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import click

from .constants import DEFAULT_HOST, DEFAULT_PORT

PID_DIR = Path.home() / ".bond-network"
PID_FILE = PID_DIR / "bondd.pid"


def _read_pid():
    try:
        return int(PID_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def _write_pid(pid):
    PID_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(pid))


def _remove_pid():
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass


def _is_process_running(pid):
    try:
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        exit_code = ctypes.wintypes.DWORD()
        kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        kernel32.CloseHandle(handle)
        return exit_code.value == 259
    except Exception:
        return False


@click.group()
def main():
    pass


@main.command("start")
@click.option("--host", default=DEFAULT_HOST, help="Host to bind")
@click.option("--port", default=DEFAULT_PORT, type=int, help="Port to bind")
@click.option("--foreground", is_flag=True, default=False, help="Run in foreground")
def start(host, port, foreground):
    pid = _read_pid()
    if pid is not None and _is_process_running(pid):
        click.echo(f"Daemon is already running (PID: {pid})")
        sys.exit(1)

    _remove_pid()

    if foreground:
        _write_pid(os.getpid())
        import uvicorn
        try:
            uvicorn.run("bond_network.api:create_app_factory", host=host, port=port, factory=True)
        finally:
            _remove_pid()
    else:
        cmd = [
            sys.executable, "-m", "bond_network.daemon_cli",
            "start", "--foreground",
            "--host", host,
            "--port", str(port),
        ]
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        )

        started = False
        for _ in range(10):
            time.sleep(0.5)
            pid = _read_pid()
            if pid is not None and _is_process_running(pid):
                started = True
                break

        if not started:
            click.echo("Failed to start daemon")
            sys.exit(1)

        click.echo(f"Daemon started (PID: {pid})")
        click.echo(f"Service address: http://{host}:{port}")


@main.command("stop")
def stop():
    pid = _read_pid()
    if pid is None:
        click.echo("Daemon is not running (no PID file)")
        sys.exit(1)

    if not _is_process_running(pid):
        _remove_pid()
        click.echo("Daemon is not running (stale PID file removed)")
        sys.exit(1)

    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=True, capture_output=True)
        _remove_pid()
        click.echo(f"Daemon stopped (PID: {pid})")
    except subprocess.CalledProcessError:
        if not _is_process_running(pid):
            _remove_pid()
            click.echo(f"Daemon stopped (PID: {pid})")
        else:
            click.echo(f"Failed to stop daemon (PID: {pid})")
            sys.exit(1)


@main.command("status")
@click.option("--port", default=DEFAULT_PORT, type=int, help="Daemon port")
def status(port):
    pid = _read_pid()
    if pid is None:
        click.echo("Daemon is not running (no PID file)")
        return

    if not _is_process_running(pid):
        _remove_pid()
        click.echo("Daemon is not running (stale PID file removed)")
        return

    click.echo(f"Daemon is running (PID: {pid})")

    try:
        url = f"http://127.0.0.1:{port}/api/network/stats"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            stats = json.loads(resp.read().decode())
            click.echo(f"  Agents: {stats.get('agent_count', 0)}")
            click.echo(f"  Bonds: {stats.get('bond_count', 0)}")
            click.echo(f"  Active emotions: {stats.get('active_emotion_count', 0)}")
    except Exception:
        click.echo("  Unable to fetch stats (service may still be starting)")


if __name__ == "__main__":
    main()
