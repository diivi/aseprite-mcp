"""list_slices must tolerate delimiter characters in a slice name."""
import json

from conftest import ok, run

from aseprite_mcp.tools import slices


def test_list_slices_handles_pipe_and_comma_in_name(sprite):
    ok(run(slices.create_slice(sprite, "weird|name,x", 1, 2, 10, 12)))
    ok(run(slices.create_slice(sprite, "ninepatch", 0, 0, 16, 16)))
    ok(run(slices.set_slice_center(sprite, "ninepatch", 4, 4, 8, 8)))
    by_name = {s["name"]: s for s in json.loads(ok(run(slices.list_slices(sprite))))}
    assert "weird|name,x" in by_name
    assert by_name["weird|name,x"]["x"] == 1 and by_name["weird|name,x"]["width"] == 10
    assert by_name["ninepatch"]["center"] == {"x": 4, "y": 4, "width": 8, "height": 8}
