"""Tests that the server survives a `server/discover` request (issue #30).

Some clients (Google Antigravity, GitHub Copilot) send `server/discover`
before `initialize`. mcp 1.6 crashed on it, so the server never started.
These tests talk to the real server over stdio and do not need Aseprite.
"""
import json
import os
import queue
import subprocess
import sys
import threading

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_server_still_initializes_after_server_discover():
    proc = subprocess.Popen(
        [sys.executable, "-m", "aseprite_mcp"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )
    lines = queue.Queue()
    threading.Thread(target=lambda: [lines.put(l) for l in proc.stdout], daemon=True).start()

    def send(message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def reply(request_id):
        while True:
            message = json.loads(lines.get(timeout=30))
            if message.get("id") == request_id:
                return message

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {}})
        assert "error" in reply(1)

        send({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        }})
        assert reply(2)["result"]["serverInfo"]["name"] == "aseprite"
    finally:
        proc.kill()
        proc.wait()
