"""Regression tests for issue #15: Lua-side errors must reach the caller.

Before the fix, `aseprite --batch --script` discarded the script's Lua
`return` value and always exited 0, so mutating tools fabricated a success
message from their input args even when the script did nothing. Every call
below feeds invalid input and asserts the tool now reports failure instead
of a fabricated success.
"""
from conftest import ok, run

from aseprite_mcp.tools import (
    animation,
    canvas,
    drawing,
    export,
    palette,
    quality,
    scene,
    transform,
)


def failed(result):
    """Assert a tool surfaced a failure rather than a fabricated success."""
    assert str(result).startswith(("Failed", "ERROR")), result
    return result


# --- issue #15 reproduction table: each must now fail loudly ---

def test_set_layer_visibility_missing_layer(sprite):
    failed(run(animation.set_layer_visibility(sprite, "NOT_A_LAYER", False)))


def test_set_frame_duration_out_of_range(sprite):
    failed(run(canvas.set_frame_duration(sprite, 99, 50)))


def test_set_tag_range_out_of_bounds(sprite):
    failed(run(animation.set_tag(sprite, "bad_tag", 5, 99)))


def test_remap_colors_missing_layer(sprite):
    failed(run(palette.remap_colors_in_cel_range(
        sprite, "NOSUCHLAYER", 1, 1, [{"from": "#D04648", "to": "#000000"}])))


def test_ensure_layers_present_all_missing(sprite):
    failed(run(quality.ensure_layers_present(sprite, ["MISSING"])))


def test_export_sprite_unwritable_format(sprite):
    # Aseprite exits 0 but writes nothing for format="json".
    failed(run(export.export_sprite(sprite, "/tmp/ase-pytest/err_out", "json")))


# --- copy_layers_between_sprites: all-missing fails; partial surfaces skips ---

def test_copy_layers_all_missing_fails(sprite, base_dir):
    target = f"{base_dir}/copy_target.aseprite"
    ok(run(canvas.create_canvas(16, 16, target)))
    failed(run(scene.copy_layers_between_sprites(sprite, target, ["BOGUS"])))


def test_copy_layers_partial_surfaces_skipped(sprite, base_dir):
    target = f"{base_dir}/copy_target2.aseprite"
    ok(run(canvas.create_canvas(16, 16, target)))
    result = run(scene.copy_layers_between_sprites(sprite, target, ["body", "BOGUS"]))
    ok(result)
    assert "skipped missing layers" in result and "BOGUS" in result, result


# --- new guards added alongside the conversion ---

def test_crop_fully_outside_canvas_rejected(sprite):
    failed(run(transform.crop_canvas(sprite, 999, 999, 10, 10)))


def test_flip_missing_layer(sprite):
    failed(run(transform.flip_layer(sprite, "NO_SUCH_LAYER", 1)))


def test_draw_line_missing_layer(sprite):
    failed(run(drawing.draw_line_at(sprite, "NO_SUCH_LAYER", 1, 0, 0, 5, 5, "#ffffff", 1)))
