"""Composite (flattened) pixel read (pixel_read.py).

Proves get_composite_* reads the VISIBLE composite (top layer wins),
unlike get_pixel_color which reads a single named cel.
"""
import json

from conftest import ok, run

from aseprite_mcp.tools import canvas, drawing, pixel_read


def test_composite_reads_top_layer(sprite):
    # fixture: 32x32, 'body' layer with a red rect at (8,8,16,16).
    ok(run(canvas.add_layer(sprite, "overlay")))
    ok(run(drawing.draw_rectangle_at(sprite, "overlay", 1, 8, 8, 16, 16, "#3050D0", True)))
    # single-cel read of the bottom 'body' layer = its own colour (red).
    body = run(pixel_read.get_pixel_color(sprite, 12, 12, "body", 1))
    assert body.lower().startswith("#d04648"), body
    # composite read = what is VISIBLE = the top overlay (blue).
    comp = run(pixel_read.get_composite_pixel(sprite, 12, 12, 1))
    assert comp.lower().startswith("#3050d0"), comp


def test_composite_rect_shape(sprite):
    px = json.loads(run(pixel_read.get_composite_rect(sprite, 8, 8, 4, 4, 1)))
    assert len(px) == 16
    assert all("hex" in p and "a" in p for p in px)


def test_composite_pixel_out_of_bounds_is_transparent(sprite):
    # A pixel far outside any content reads as transparent black.
    res = run(pixel_read.get_composite_pixel(sprite, 1, 1, 1))
    assert "a=0" in res, res
