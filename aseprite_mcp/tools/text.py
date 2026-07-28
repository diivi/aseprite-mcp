"""Text drawing.

Aseprite exposes no text API to Lua, so glyphs are rasterised here and the
result is blitted into the sprite as an image.
"""

import os
import tempfile
from typing import Optional

from PIL import Image

from ..core.commands import AsepriteCommand, lua_escape
from ..core.colors import parse_hex_color
from ..core.lua import FIND_LAYER, NORMALIZE_CEL
from ..core import fonts as fontlib
from .. import mcp

_ANCHORS = (
    "topleft", "top", "topright",
    "left", "center", "right",
    "bottomleft", "bottom", "bottomright",
    "baselineleft", "baseline", "baselineright",
)


def _text_origin(anchor: str, x: int, y: int, metrics: dict) -> tuple[int, int]:
    """Map an anchor point to the pen origin the glyph run should start from.

    Ink coordinates run from the pen origin on x and from the baseline on y, so
    the baseline* anchors need no vertical correction at all while the box
    anchors are offset by the ink extents.
    """
    width, height = metrics["width"], metrics["height"]

    if anchor.endswith("right"):
        x -= width
    elif anchor in ("top", "center", "bottom", "baseline"):
        x -= width // 2
    origin_x = x - metrics["left"]

    if anchor.startswith("baseline"):
        return origin_x, y
    if anchor.startswith("bottom"):
        y -= height
    elif anchor in ("left", "center", "right"):
        y -= height // 2
    return origin_x, y - metrics["top"]


@mcp.tool()
async def list_text_fonts() -> str:
    """List fonts that draw_text can use.

    Covers bitmap sprite-sheet fonts and .ttf/.otf files installed under
    ~/.aseprite-mcp/fonts, plus TrueType fonts found in the system font
    directories. Bitmap fonts are the right choice for pixel art: their
    glyphs are already pixels and `size` scales them by whole numbers.
    """
    try:
        found = fontlib.available_fonts()
    except Exception as exc:                                # pragma: no cover
        return f"ERROR: {exc}"
    if not found:
        return "No fonts found. Drop a .ttf into ~/.aseprite-mcp/fonts/."

    user = [f for f in found if f["source"] == "user"]
    system = [f for f in found if f["source"] == "system"]
    lines = []
    if user:
        lines.append("User fonts (~/.aseprite-mcp/fonts):")
        lines += [f"  {f['name']}  [{f['kind']}]" for f in user]
    if system:
        lines.append(f"System fonts ({len(system)}, all truetype):")
        lines += [f"  {f['name']}" for f in system]
    return "\n".join(lines)


@mcp.tool()
async def measure_text(
    text: str,
    font: str,
    size: int = 1,
    letter_spacing: int = 0,
    bold: int = 0,
    antialias: bool = False,
) -> str:
    """Measure text without drawing it.

    Use this to size a panel or centre a label in one shot instead of
    guessing and re-rendering.

    Args:
        text: The string to measure
        font: Font name from list_text_fonts, or a path to a .ttf/.otf or
            bitmap font directory
        size: Pixel size for TrueType fonts; integer scale factor for bitmap
            fonts (default 1)
        letter_spacing: Extra pixels between glyphs (default 0)
        bold: Faux-bold passes; each grows strokes by 1px (default 0)
        antialias: Keep greyscale edges instead of hard pixels (default False)

    Returns:
        width, height, advance_width, and the ink extents above/below the
        baseline.
    """
    try:
        f = fontlib.load_font(font)
        _, m = fontlib.shape(text, f, size, letter_spacing, bold, antialias)
    except Exception as exc:
        return f"ERROR: {exc}"
    return (
        f"width={m['width']} height={m['height']} advance_width={m['advance_width']} "
        f"above_baseline={-m['top']} below_baseline={m['bottom'] + 1} "
        f"left_bearing={m['left']}"
    )


@mcp.tool()
async def draw_text(
    filename: str,
    text: str,
    x: int,
    y: int,
    font: str,
    size: int = 1,
    color: str = "#FFFFFF",
    layer_name: Optional[str] = None,
    frame_index: int = 1,
    anchor: str = "topleft",
    letter_spacing: int = 0,
    bold: int = 0,
    outline_color: Optional[str] = None,
    outline_width: int = 1,
    outline_diagonal: bool = True,
    shadow_color: Optional[str] = None,
    shadow_dx: int = 1,
    shadow_dy: int = 1,
    antialias: bool = False,
    create_if_missing: bool = True,
) -> str:
    """Draw text onto a sprite.

    Glyphs are rasterised outside Aseprite and composited in, because the
    Lua API has no text drawing of its own.

    Args:
        filename: Aseprite file to modify
        text: String to draw
        x: X coordinate of the anchor point
        y: Y coordinate of the anchor point
        font: Font name from list_text_fonts, or a path to a .ttf/.otf or a
            bitmap font directory
        size: Pixel size for TrueType fonts; integer scale factor for bitmap
            fonts (default 1)
        color: Text colour, #RRGGBB or #RRGGBBAA (default white)
        layer_name: Layer to draw on; the active/first layer if omitted
        frame_index: Frame index starting at 1 (default 1)
        anchor: Which point of the text (x, y) refers to - one of topleft,
            top, topright, left, center, right, bottomleft, bottom,
            bottomright, baselineleft, baseline, baselineright
            (default topleft)
        letter_spacing: Extra pixels between glyphs (default 0)
        bold: Faux-bold passes; each grows strokes by 1px (default 0)
        outline_color: If set, draw a 1px outline in this colour
        outline_width: Outline thickness in pixels (default 1)
        outline_diagonal: Include diagonal neighbours in the outline, giving a
            rounded corner; False gives a boxier 4-way outline (default True)
        shadow_color: If set, draw a drop shadow in this colour
        shadow_dx: Shadow X offset (default 1)
        shadow_dy: Shadow Y offset (default 1)
        antialias: Keep greyscale edges instead of hard pixels (default False)
        create_if_missing: Create the layer/cel if absent (default True)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if anchor not in _ANCHORS:
        return f"Invalid anchor '{anchor}'. Expected one of: {', '.join(sorted(_ANCHORS))}"

    fill = parse_hex_color(color)
    if fill is None:
        return f"Invalid color value: {color}"
    outline_rgba = None
    if outline_color:
        outline_rgba = parse_hex_color(outline_color)
        if outline_rgba is None:
            return f"Invalid outline_color value: {outline_color}"
    shadow_rgba = None
    if shadow_color:
        shadow_rgba = parse_hex_color(shadow_color)
        if shadow_rgba is None:
            return f"Invalid shadow_color value: {shadow_color}"

    try:
        f = fontlib.load_font(font)
        ink, metrics = fontlib.shape(text, f, size, letter_spacing, bold, antialias)
    except Exception as exc:
        return f"ERROR: {exc}"
    if not ink:
        return "OK: nothing to draw (text has no visible glyphs)"

    # Build the layers of the stamp, back to front.
    outline = set()
    if outline_rgba:
        outline = set(ink)
        for _ in range(max(1, outline_width)):
            grown = set(outline)
            for px, py in outline:
                grown.update({(px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)})
                if outline_diagonal:
                    grown.update({(px - 1, py - 1), (px + 1, py - 1),
                                  (px - 1, py + 1), (px + 1, py + 1)})
            outline = grown
        outline -= ink
    shadow = {(px + shadow_dx, py + shadow_dy) for px, py in ink} if shadow_rgba else set()
    shadow -= ink | outline

    everything = ink | outline | shadow
    min_x = min(p[0] for p in everything)
    min_y = min(p[1] for p in everything)
    max_x = max(p[0] for p in everything)
    max_y = max(p[1] for p in everything)
    w, h = max_x - min_x + 1, max_y - min_y + 1

    # The anchor is resolved against the glyph box alone, so adding an outline
    # or a shadow never shifts where the letters themselves land.
    origin_x, origin_y = _text_origin(anchor, x, y, metrics)

    stamp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = stamp.load()
    for group, rgba in ((shadow, shadow_rgba), (outline, outline_rgba), (ink, fill)):
        if not rgba:
            continue
        for gx, gy in group:
            px[gx - min_x, gy - min_y] = rgba

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    stamp.save(tmp.name)

    blit_x = origin_x + min_x
    blit_y = origin_y + min_y
    safe_png = lua_escape(os.path.abspath(tmp.name).replace("\\", "/"))
    layer_lookup = (
        f'local target = find_layer(spr, "{lua_escape(layer_name)}")'
        if layer_name else
        "local target = app.activeLayer or spr.layers[1]"
    )
    create_layer = (
        f'''
        if not target then
            if not {str(create_if_missing).lower()} then print("ERROR:Layer not found") return end
            target = spr:newLayer()
            target.name = "{lua_escape(layer_name)}"
        end''' if layer_name else
        '''
        if not target then print("ERROR:No layer to draw on") return end'''
    )

    script = f"""
    {FIND_LAYER}
    {NORMALIZE_CEL}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then print("ERROR:Frame index out of range") return end

    local stamp = Image{{ fromFile = "{safe_png}" }}
    if not stamp then print("ERROR:Could not load rendered text") return end

    {layer_lookup}
    app.transaction(function()
        {create_layer}
        local cel = normalize_cel(spr, target, spr.frames[idx], true)
        cel.image:drawImage(stamp, Point({blit_x}, {blit_y}), 255, BlendMode.NORMAL)
    end)

    spr:saveAs(spr.filename)
    print("OK")
    """

    try:
        success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    if not success:
        return f"Error drawing text: {output}"
    return (f"Drew '{text}' at ({blit_x}, {blit_y}), "
            f"text box {metrics['width']}x{metrics['height']}, stamp {w}x{h}")
