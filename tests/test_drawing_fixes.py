"""B3 (cel-normalization, no silent clip) + B4 (per-pixel alpha) fixes."""
from conftest import ok, run

from aseprite_mcp.tools import canvas, drawing, pixel_read


def _rgba(pixel_result: str) -> tuple[int, int, int, int]:
    s = str(pixel_result)
    return (int(s.split("r=")[1].split(",")[0]),
            int(s.split("g=")[1].split(",")[0]),
            int(s.split("b=")[1].split(",")[0]),
            int(s.split("a=")[1].split(")")[0]))


def test_polygon_offcanvas_vertices_no_clip(sprite):
    # Two vertices are outside the 32x32 canvas; pset() must bounds-guard
    # (no crash) and the in-canvas fill must still land at sprite-global (16,16).
    ok(run(canvas.add_layer(sprite, "poly")))
    pts = [{"x": 16, "y": -5}, {"x": -5, "y": 30}, {"x": 30, "y": 30}]
    ok(run(drawing.draw_polygon(sprite, "poly", 1, pts, "#00FF00", True, True)))
    r, g, b, _ = _rgba(run(pixel_read.get_pixel_color(sprite, 16, 16, "poly", 1)))
    assert (r, g, b) == (0, 255, 0), (r, g, b)


def test_gradient_lands_at_sprite_global(sprite):
    ok(run(canvas.add_layer(sprite, "grad")))
    ok(run(drawing.apply_gradient_rect(sprite, "grad", 1, 4, 4, 16, 1,
                                       "#000000", "#FFFFFF", True, True)))
    left = _rgba(run(pixel_read.get_pixel_color(sprite, 4, 4, "grad", 1)))
    right = _rgba(run(pixel_read.get_pixel_color(sprite, 19, 4, "grad", 1)))
    assert left[0] < right[0], (left, right)  # dark -> light, left to right


def test_draw_accepts_rgba_alpha(sprite):
    # "#RRGGBBAA" was rejected before B4 (len != 6) and left the layer empty.
    ok(run(canvas.add_layer(sprite, "alpha")))
    ok(run(drawing.draw_pixels_at(sprite, "alpha", 1,
                                  [{"x": 6, "y": 6, "color": "#FF000080"}], True)))
    r, g, b, a = _rgba(run(pixel_read.get_pixel_color(sprite, 6, 6, "alpha", 1)))
    assert (r, g, b) == (255, 0, 0)
    assert a == 0x80  # semi-transparency preserved


def test_draw_accepts_short_hex(sprite):
    ok(run(canvas.add_layer(sprite, "short")))
    ok(run(drawing.draw_pixels_at(sprite, "short", 1,
                                  [{"x": 5, "y": 5, "color": "#0F0"}], True)))
    assert _rgba(run(pixel_read.get_pixel_color(sprite, 5, 5, "short", 1))) == (0, 255, 0, 255)


def test_draw_rejects_bad_hex(sprite):
    ok(run(canvas.add_layer(sprite, "bad")))
    res = run(drawing.draw_pixels_at(sprite, "bad", 1,
                                     [{"x": 0, "y": 0, "color": "#GG0000"}], True))
    assert res.startswith(("Invalid", "Failed"))
