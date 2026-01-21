import os
import subprocess
import sys
import tempfile
import signal
from .. import mcp

def _pid_path(port: int) -> str:
    return os.path.join(tempfile.gettempdir(), f"aseprite_mcp_preview_{port}.pid")

def _pid_is_running(pid: int) -> bool:
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                check=False,
                capture_output=True,
                text=True
            )
            return str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False

@mcp.tool()
async def start_preview_server(directory: str, port: int = 8000) -> str:
    """Start a simple HTTP server to preview exported sprites.

    Args:
        directory: Directory to serve
        port: Port to bind (default 8000)
    """
    if not os.path.isdir(directory):
        return f"Directory {directory} not found"

    pid_file = _pid_path(port)
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r", encoding="utf-8") as f:
                pid = int(f.read().strip())
            if _pid_is_running(pid):
                return f"Preview server may already be running on port {port}"
        except Exception:
            pass
        os.remove(pid_file)

    args = [sys.executable, "-m", "http.server", str(port), "--directory", directory]
    popen_kwargs = {"cwd": directory, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        popen_kwargs["start_new_session"] = True
    proc = subprocess.Popen(args, **popen_kwargs)
    with open(pid_file, "w", encoding="utf-8") as f:
        f.write(str(proc.pid))

    return f"Preview server started: http://localhost:{port}/"

@mcp.tool()
async def stop_preview_server(port: int = 8000) -> str:
    """Stop the preview HTTP server for a given port.

    Args:
        port: Port to stop (default 8000)
    """
    pid_file = _pid_path(port)
    if not os.path.exists(pid_file):
        return f"No preview server PID found for port {port}"

    with open(pid_file, "r", encoding="utf-8") as f:
        pid = int(f.read().strip())

    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
    finally:
        os.remove(pid_file)

    return f"Preview server stopped on port {port}"
