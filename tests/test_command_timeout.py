"""Tests for the Aseprite run timeout (issue #38).

`run_command` used to call `subprocess.run` with no timeout, so one Aseprite
process that never exited blocked the server forever. These tests point
ASEPRITE_PATH at tiny shell scripts, so they do not need Aseprite installed.
"""
import os
import subprocess
import time

import pytest

from aseprite_mcp.core import commands
from aseprite_mcp.core.commands import DEFAULT_TIMEOUT_SECONDS, AsepriteCommand, command_timeout

pytestmark = pytest.mark.skipif(os.name == "nt", reason="uses /bin/sh scripts")


def fake_aseprite(tmp_path, monkeypatch, body):
    """Make ASEPRITE_PATH a shell script running `body`."""
    script = tmp_path / "fake-aseprite"
    script.write_text(f"#!/bin/sh\n{body}\n")
    script.chmod(0o755)
    monkeypatch.setenv("ASEPRITE_PATH", str(script))


def test_stuck_command_is_stopped(tmp_path, monkeypatch):
    pid_file = tmp_path / "pid"
    fake_aseprite(tmp_path, monkeypatch, f'echo $$ > "{pid_file}"\nexec sleep 30')
    monkeypatch.setenv("ASEPRITE_TIMEOUT_SECONDS", "1")

    start = time.monotonic()
    success, output = AsepriteCommand.run_command(["--batch"])
    elapsed = time.monotonic() - start

    assert success is False
    assert "did not finish within 1s" in output
    assert elapsed < 10
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)


def test_quick_command_still_succeeds(tmp_path, monkeypatch):
    fake_aseprite(tmp_path, monkeypatch, "echo done")
    assert AsepriteCommand.run_command(["--batch"]) == (True, "done\n")


def test_failing_command_still_returns_stderr(tmp_path, monkeypatch):
    fake_aseprite(tmp_path, monkeypatch, "echo boom >&2\nexit 3")
    assert AsepriteCommand.run_command(["--batch"]) == (False, "boom\n")


def test_command_does_not_read_the_servers_stdin(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(commands.subprocess, "run", fake_run)
    AsepriteCommand.run_command(["--batch"])
    assert seen["stdin"] is subprocess.DEVNULL


@pytest.mark.parametrize("value, expected", [
    (None, DEFAULT_TIMEOUT_SECONDS),
    ("5", 5.0),
    ("0.5", 0.5),
    ("0", DEFAULT_TIMEOUT_SECONDS),
    ("-3", DEFAULT_TIMEOUT_SECONDS),
    ("soon", DEFAULT_TIMEOUT_SECONDS),
    ("inf", DEFAULT_TIMEOUT_SECONDS),
    ("nan", DEFAULT_TIMEOUT_SECONDS),
])
def test_command_timeout_from_environment(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("ASEPRITE_TIMEOUT_SECONDS", raising=False)
    else:
        monkeypatch.setenv("ASEPRITE_TIMEOUT_SECONDS", value)
    assert command_timeout() == expected
