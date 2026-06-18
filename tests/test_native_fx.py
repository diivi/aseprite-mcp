"""Native Aseprite command wrappers (native_fx.py)."""
import json

from conftest import ok, run

from aseprite_mcp.tools import native_fx, pixel_read


def _hex(pixel_result: str) -> str:
    """Extract the leading '#rrggbb' from get_pixel_color's output."""
    return str(pixel_result).split()[0].lower()


def test_list_convolution_matrices():
    names = json.loads(run(native_fx.list_convolution_matrices()))
    assert "blur-3x3" in names
    assert "sharpen-3x3" in names
    assert "misc-emboss" in names


def test_apply_convolution_rejects_unknown_matrix(sprite):
    res = run(native_fx.apply_convolution(sprite, "not-a-matrix", "body", 1))
    assert res.startswith("Unknown matrix")


def test_outline_native_inside_colours_the_edge(sprite):
    # 'body' has a red rect at (8,8)-(23,23). An inside outline recolours the
    # outer ring, so the left edge at (8, 12) becomes the outline colour.
    ok(run(native_fx.outline_native(sprite, "body", 1, "#00FF00", "inside", "circle")))
    edge = run(pixel_read.get_pixel_color(sprite, 8, 12, "body", 1))
    assert _hex(edge).startswith("#00ff00"), edge


def test_invert_colors_is_exact(sprite):
    before = run(pixel_read.get_pixel_color(sprite, 12, 12, "body", 1))
    r, g, b = (int(before.split("r=")[1].split(",")[0]),
               int(before.split("g=")[1].split(",")[0]),
               int(before.split("b=")[1].split(",")[0]))
    ok(run(native_fx.invert_colors(sprite, "body", 1)))
    after = run(pixel_read.get_pixel_color(sprite, 12, 12, "body", 1))
    expected = f"#{255 - r:02x}{255 - g:02x}{255 - b:02x}"
    assert _hex(after).startswith(expected), (before, after, expected)


def test_adjust_hsl_native(sprite):
    ok(run(native_fx.adjust_hsl_native(sprite, "body", 1, 40, 0, 0)))


def test_adjust_brightness_contrast(sprite):
    ok(run(native_fx.adjust_brightness_contrast(sprite, "body", 1, 30, 10)))


def test_apply_convolution_blur(sprite):
    ok(run(native_fx.apply_convolution(sprite, "blur-3x3", "body", 1)))


def test_adjust_hsl_native_rejects_out_of_range(sprite):
    assert run(native_fx.adjust_hsl_native(sprite, "body", 1, 999)).startswith("hue must be")


def test_extract_palette(sprite):
    result = json.loads(ok(run(native_fx.extract_palette(sprite, 16))))
    assert result["count"] >= 1
    assert all(c.startswith("#") and len(c) == 7 for c in result["colors"])
