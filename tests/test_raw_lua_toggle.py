"""Registration tests for the optional arbitrary Lua tool."""
import json
import os
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]


def registered_tool_names(raw_lua_setting=None):
    env = os.environ.copy()
    env.pop("ASEPRITE_ENABLE_RAW_LUA", None)
    if raw_lua_setting is not None:
        env["ASEPRITE_ENABLE_RAW_LUA"] = raw_lua_setting
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import asyncio, json; from aseprite_mcp import mcp; "
            "import aseprite_mcp.tools; "
            "print(json.dumps([tool.name for tool in asyncio.run(mcp.list_tools())]))",
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_raw_lua_tool_is_disabled_by_default():
    names = registered_tool_names()

    assert "run_lua_script" not in names
    assert "draw_rows" in names
    assert "view_sprite" in names


def test_raw_lua_tool_requires_explicit_opt_in():
    names = registered_tool_names("true")

    assert "run_lua_script" in names
    assert "draw_rows" in names
    assert "view_sprite" in names
