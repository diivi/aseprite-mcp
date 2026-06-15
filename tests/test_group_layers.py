"""Issue #17: layer lookups must reach layers nested inside groups.

Before the fix every tool resolved a layer by scanning only the sprite's
top-level layers, so a layer inside a group was unreachable by name. These
tests build a grouped sprite and assert the operation tools now reach nested
layers by bare name and by "group/child" path, that a bare name prefers the
shallower layer when names collide, and that the duplicate-name guard stays
top-level (Aseprite permits the same name in different groups).
"""
import pytest

from conftest import BASE, ok, run

from aseprite_mcp.tools import (
    animation,
    canvas,
    drawing,
    layers,
    pixel_read,
    tilemap,
    transform,
)
from aseprite_mcp.core.commands import AsepriteCommand


@pytest.fixture(scope="module")
def nested(base_dir):
    """A sprite with GRP{inside}, top-level outer, and a 'dupe' in both places."""
    path = f"{BASE}/group_layers.aseprite"
    ok(run(canvas.create_canvas(16, 16, path)))
    setup = """
    local spr = app.activeSprite
    local grp = spr:newGroup(); grp.name = "GRP"
    local inside = spr:newLayer(); inside.name = "inside"; inside.parent = grp
    spr:newCel(inside, spr.frames[1], Image(16, 16, spr.colorMode), Point(0, 0))
    local outer = spr:newLayer(); outer.name = "outer"
    local d1 = spr:newLayer(); d1.name = "dupe"
    local d2 = spr:newLayer(); d2.name = "dupe"; d2.parent = grp
    spr:saveAs(spr.filename)
    """
    success, out = AsepriteCommand.execute_lua_script(setup, path)
    assert success, out
    return path


def test_draw_reaches_nested_by_name(nested):
    ok(run(drawing.draw_rectangle_at(nested, "inside", 1, 0, 0, 4, 4, "#ffffff", True)))


def test_draw_reaches_nested_by_path(nested):
    ok(run(drawing.draw_rectangle_at(nested, "GRP/inside", 1, 2, 2, 4, 4, "#00ff00", True)))


def test_visibility_reaches_nested(nested):  # animation.py converted loop
    ok(run(animation.set_layer_visibility(nested, "inside", False)))


def test_rename_reaches_nested(nested):  # layers.py via the shared helper
    ok(run(layers.rename_layer(nested, "outer", "outer_renamed")))


def test_flip_reaches_nested(nested):  # transform.py converted loop
    ok(run(transform.flip_layer(nested, "inside", 1, "horizontal")))


def test_pixel_read_reaches_nested(nested):  # pixel_read.py converted loop
    result = run(pixel_read.get_pixel_color(nested, 0, 0, "inside"))
    assert not str(result).startswith(("Failed", "ERROR")), result


def test_ambiguous_bare_name_prefers_shallow(nested):
    # 'dupe' exists top-level and inside GRP; the bare name must resolve to the
    # shallower one, while the path targets the nested namesake.
    ok(run(drawing.draw_rectangle_at(nested, "dupe", 1, 0, 0, 2, 2, "#ff0000", True)))
    ok(run(drawing.draw_rectangle_at(nested, "GRP/dupe", 1, 0, 0, 2, 2, "#0000ff", True)))


def test_bogus_name_still_fails(nested):
    result = run(drawing.draw_rectangle_at(nested, "NOPE", 1, 0, 0, 2, 2, "#ffffff", True))
    assert str(result).startswith(("Failed", "ERROR")), result


def test_duplicate_name_across_group_allowed(nested):
    # 'inside' exists only inside GRP, so creating a top-level layer with that
    # name must be allowed — the duplicate guard is top-level only.
    result = run(tilemap.create_tilemap_layer(nested, "inside", 8, 8))
    assert not str(result).startswith(("Failed", "ERROR")), result


@pytest.fixture(scope="module")
def slashed(base_dir):
    """Aseprite permits "/" inside a name. Build a group literally named
    'abc/x' holding child 'y', plus a genuine 'abc' -> 'x' -> 'z' hierarchy
    that shares the leading token, so path navigation must coexist with
    "/"-in-name and backtrack when the longest prefix dead-ends."""
    path = f"{BASE}/slashed_groups.aseprite"
    ok(run(canvas.create_canvas(16, 16, path)))
    setup = """
    local spr = app.activeSprite
    local g = spr:newGroup(); g.name = "abc/x"
    local y = spr:newLayer(); y.name = "y"; y.parent = g
    spr:newCel(y, spr.frames[1], Image(16, 16, spr.colorMode), Point(0, 0))
    local a = spr:newGroup(); a.name = "abc"
    local x = spr:newGroup(); x.name = "x"; x.parent = a
    local z = spr:newLayer(); z.name = "z"; z.parent = x
    spr:newCel(z, spr.frames[1], Image(16, 16, spr.colorMode), Point(0, 0))
    spr:saveAs(spr.filename)
    """
    success, out = AsepriteCommand.execute_lua_script(setup, path)
    assert success, out
    return path


def test_child_under_slash_named_group(slashed):
    # The group is literally named "abc/x"; its child "y" must resolve as
    # "abc/x/y" — the longest leading group name wins.
    ok(run(drawing.draw_rectangle_at(slashed, "abc/x/y", 1, 0, 0, 4, 4, "#ffffff", True)))


def test_real_path_backtracks_past_slash_name(slashed):
    # "abc/x/z" must still reach the genuine abc -> x -> z layer: the longest
    # prefix "abc/x" matches the sibling group but has no child "z", so the
    # walk backtracks to "abc" -> "x" -> "z".
    ok(run(drawing.draw_rectangle_at(slashed, "abc/x/z", 1, 0, 0, 4, 4, "#00ff00", True)))
