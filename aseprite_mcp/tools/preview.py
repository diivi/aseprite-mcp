import os
import subprocess
import tempfile
from .. import mcp

def _pid_path(port: int) -> str:
    return os.path.join(tempfile.gettempdir(), f"aseprite_mcp_preview_{port}.pid")

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
        return f"Preview server may already be running on port {port}"

    python_exe = os.path.join(os.path.dirname(os.__file__), "python.exe")
    if not os.path.exists(python_exe):
        python_exe = "python"

    args = [python_exe, "-m", "http.server", str(port), "--directory", directory]
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    proc = subprocess.Popen(args, cwd=directory, creationflags=creationflags)
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
        pid = f.read().strip()

    try:
        subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], check=False, capture_output=True)
    finally:
        os.remove(pid_file)

    return f"Preview server stopped on port {port}"
