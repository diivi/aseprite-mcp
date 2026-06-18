"""Issue #17 follow-up: create layers and groups inside named groups.

add_layer / duplicate_layer used to create only at the top level; add_group
did not exist. These tests check that a group can be created (optionally
nested), that a new or duplicated layer lands inside a named group (resolved
by name or "group/subgroup" path), and that a bad / non-group target fails.
"""
import json

import pytest

from conftest import BASE, ok, run
from aseprite_mcp.tools import animation, canvas, drawing, layers


def _top_level(path):
    """Map of top-level layer name -> is_group.

    get_sprite_info now enumerates nested layers too (each with a "parent"),
    so filter to parent==None for the top level.
    """
    info = json.loads(run(animation.get_sprite_info(path)))
    return {layer["name"]: layer["is_group"]
            for layer in info["layers"] if layer.get("parent") is None}


@pytest.fixture
def fresh(base_dir, request):
    path = f"{BASE}/cig_{request.node.name}.aseprite"
    ok(run(canvas.create_canvas(16, 16, path)))
    return path


def test_add_group_top_level(fresh):
    ok(run(canvas.add_group(fresh, "GRP")))
    assert _top_level(fresh).get("GRP") is True


def test_add_layer_into_group(fresh):
    ok(run(canvas.add_group(fresh, "GRP")))
    ok(run(canvas.add_layer(fresh, "child", "GRP")))
    assert "child" not in _top_level(fresh), "child must be inside GRP, not top level"
    # reachable by path and (recursively) by bare name
    ok(run(drawing.draw_rectangle_at(fresh, "GRP/child", 1, 0, 0, 4, 4, "#ffffff", True)))
    ok(run(layers.rename_layer(fresh, "child", "child_renamed")))


def test_add_group_nested_then_layer_two_deep(fresh):
    ok(run(canvas.add_group(fresh, "GRP")))
    ok(run(canvas.add_group(fresh, "SUB", "GRP")))
    assert "SUB" not in _top_level(fresh), "SUB must be inside GRP"
    ok(run(canvas.add_layer(fresh, "deep", "GRP/SUB")))
    ok(run(drawing.draw_rectangle_at(fresh, "GRP/SUB/deep", 1, 0, 0, 2, 2, "#ffffff", True)))


def test_duplicate_into_group(fresh):
    ok(run(canvas.add_layer(fresh, "body")))
    ok(run(drawing.draw_rectangle_at(fresh, "body", 1, 0, 0, 8, 8, "#D04648", True)))
    ok(run(canvas.add_group(fresh, "GRP")))
    ok(run(layers.duplicate_layer(fresh, "body", "body_copy", "GRP")))
    assert "body_copy" not in _top_level(fresh), "copy must be inside GRP"
    ok(run(drawing.draw_rectangle_at(fresh, "GRP/body_copy", 1, 0, 0, 2, 2, "#ffffff", True)))


def test_add_layer_unknown_group_fails(fresh):
    result = run(canvas.add_layer(fresh, "child", "NOPE"))
    assert str(result).startswith(("Failed", "ERROR")), result


def test_add_layer_target_not_a_group_fails(fresh):
    ok(run(canvas.add_layer(fresh, "plain")))  # a normal layer, not a group
    result = run(canvas.add_layer(fresh, "child", "plain"))
    assert str(result).startswith(("Failed", "ERROR")), result
