"""Text rendering (tools/text.py, core/fonts.py).

The bitmap tests build their own font on disk so they run anywhere; only the
TrueType tests need something installed, and they skip when nothing is found.
"""
import json
import os

import pytest
from conftest import ok, run
from PIL import Image

from aseprite_mcp.core import fonts as fontlib
from aseprite_mcp.tools import pixel_read, text

# A 4x6 sheet font covering "ABO", laid out the way font.json describes it:
# one 4x6 cell per glyph, ink is any non-transparent pixel, baseline at row 5.
FIXTURE_GLYPHS = {
    "A": [".##.", "#..#", "####", "#..#", "#..#", "...."],
    "B": ["###.", "#..#", "###.", "#..#", "###.", "...."],
    "O": [".##.", "#..#", "#..#", "#..#", ".##.", "...."],
}
CELL_W, CELL_H, ASCENT = 4, 6, 5


@pytest.fixture(scope="module")
def bitmap_font(tmp_path_factory):
    """A minimal bitmap font directory, returned as a path for `font=`."""
    directory = tmp_path_factory.mktemp("fixture-font")
    chars = "ABO"
    sheet = Image.new("RGBA", (CELL_W * len(chars), CELL_H), (0, 0, 0, 0))
    for index, char in enumerate(chars):
        for y, row in enumerate(FIXTURE_GLYPHS[char]):
            for x, cell in enumerate(row):
                if cell == "#":
                    sheet.putpixel((index * CELL_W + x, y), (255, 255, 255, 255))
    sheet.save(directory / "sheet.png")
    (directory / "font.json").write_text(json.dumps({
        "name": "fixture",
        "letter_gap": 1,
        "space_width": 2,
        "sheets": [{
            "file": "sheet.png",
            "cell_w": CELL_W, "cell_h": CELL_H, "ascent": ASCENT,
            "chars": [chars],
        }],
    }))
    fontlib.clear_cache()
    return str(directory)


def _system_truetype():
    for entry in fontlib.available_fonts():
        if entry["kind"] == "truetype":
            return entry["path"]
    return None


# ── discovery / errors ────────────────────────────────────────────────

def test_unknown_font_is_reported():
    out = run(text.measure_text("ABC", "definitely-not-a-font"))
    assert out.startswith("ERROR")
    assert "not found" in out


def test_list_fonts_never_raises():
    out = run(text.list_text_fonts())
    assert not out.startswith("ERROR")


def test_bitmap_font_rejects_zero_size(bitmap_font):
    out = run(text.measure_text("A", bitmap_font, 0))
    assert out.startswith("ERROR")
    assert "scale factor" in out


def test_rejects_bad_anchor(sprite, bitmap_font):
    out = run(text.draw_text(sprite, "A", 0, 0, bitmap_font, anchor="middle"))
    assert "Invalid anchor" in out


# ── measurement ───────────────────────────────────────────────────────

def test_measure_matches_the_fixture_geometry(bitmap_font):
    out = run(text.measure_text("A", bitmap_font, 1))
    # 4px of ink, +1 letter_gap of advance; 5 inked rows, all above the baseline.
    assert "width=4" in out
    assert "height=5" in out
    assert "advance_width=5" in out
    assert "above_baseline=5" in out


def test_measure_scales_with_size(bitmap_font):
    one = run(text.measure_text("AB", bitmap_font, 1))
    two = run(text.measure_text("AB", bitmap_font, 2))
    assert "height=5" in one and "height=10" in two
    # advance per glyph is 4px of ink + 1px letter_gap.
    assert "advance_width=10" in one and "advance_width=20" in two


def test_letter_spacing_widens_the_advance(bitmap_font):
    tight = run(text.measure_text("AB", bitmap_font, 1, letter_spacing=0))
    loose = run(text.measure_text("AB", bitmap_font, 1, letter_spacing=3))
    assert "advance_width=10" in tight
    assert "advance_width=13" in loose


def test_bold_thickens_the_ink(bitmap_font):
    font = fontlib.load_font(bitmap_font)
    plain, _ = fontlib.shape("O", font, 2)
    bold, _ = fontlib.shape("O", font, 2, bold=1)
    assert len(bold) > len(plain)
    assert plain <= bold, "bold must be a superset, not a reflow"


def test_glyphs_share_a_baseline(bitmap_font):
    """Every glyph must sit on one baseline or a word visibly steps."""
    font = fontlib.load_font(bitmap_font)
    bottoms = {fontlib.shape(ch, font, 2)[1]["bottom"] for ch in "ABO"}
    assert len(bottoms) == 1, f"glyphs disagree on the baseline: {bottoms}"


def test_unmapped_characters_are_skipped(bitmap_font):
    """An unknown codepoint contributes nothing rather than raising."""
    assert run(text.measure_text("A?", bitmap_font, 1)) == \
           run(text.measure_text("A", bitmap_font, 1))


def test_overrides_replace_a_sheet_glyph(tmp_path, bitmap_font):
    """font.json overrides let a caller repair a glyph the sheet gets wrong."""
    spec = json.loads(open(os.path.join(bitmap_font, "font.json")).read())
    spec["overrides"] = {str(ord("A")): {"ascent": ASCENT, "rows": ["####"] * 5}}
    patched = tmp_path / "patched"
    patched.mkdir()
    (patched / "sheet.png").write_bytes(open(os.path.join(bitmap_font, "sheet.png"), "rb").read())
    (patched / "font.json").write_text(json.dumps(spec))

    fontlib.clear_cache()
    ink, _ = fontlib.shape("A", fontlib.load_font(str(patched)), 1)
    assert len(ink) == 20, "override rows should be used verbatim"
    fontlib.clear_cache()


# ── drawing ───────────────────────────────────────────────────────────

def test_draw_text_puts_ink_on_the_canvas(sprite, bitmap_font):
    out = ok(run(text.draw_text(sprite, "O", 4, 4, bitmap_font, size=1,
                                color="#FF0000", layer_name="body")))
    assert "Drew" in out
    # 'O' has ink at (1,0) of its box, which lands at (5,4) on the sprite.
    px = ok(run(pixel_read.get_pixel_color(sprite, 5, 4, "body", 1)))
    assert "#ff0000" in px.lower()


def test_topleft_anchor_places_the_box_at_the_point(sprite, bitmap_font):
    out = ok(run(text.draw_text(sprite, "B", 10, 10, bitmap_font, size=1,
                                color="#00FF00", layer_name="body")))
    assert "at (10, 10)" in out


def test_center_anchor_is_offset_by_half_the_box(sprite, bitmap_font):
    out = ok(run(text.draw_text(sprite, "B", 20, 20, bitmap_font, size=1,
                                color="#0000FF", layer_name="body",
                                anchor="center")))
    # box is 4x5, so the top-left lands 2 left and 2 up of the anchor.
    assert "at (18, 18)" in out


def test_outline_grows_the_stamp_but_not_the_box(sprite, bitmap_font):
    plain = ok(run(text.draw_text(sprite, "O", 4, 14, bitmap_font, size=1,
                                  color="#FFFFFF", layer_name="body")))
    outlined = ok(run(text.draw_text(sprite, "O", 14, 14, bitmap_font, size=1,
                                     color="#FFFFFF", layer_name="body",
                                     outline_color="#000000")))
    assert "text box 4x5" in plain and "text box 4x5" in outlined
    assert "stamp 4x5" in plain and "stamp 6x7" in outlined


def test_empty_text_is_a_no_op(sprite, bitmap_font):
    out = run(text.draw_text(sprite, "", 0, 0, bitmap_font))
    assert out.startswith("OK")


# ── truetype ──────────────────────────────────────────────────────────

def test_truetype_renders_hard_pixels_by_default():
    path = _system_truetype()
    if not path:
        pytest.skip("no TrueType font available on this machine")
    font = fontlib.load_font(path)
    ink, metrics = fontlib.shape("A", font, 24)
    assert ink, "expected some ink"
    assert metrics["height"] > 1
