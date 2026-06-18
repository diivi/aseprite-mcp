"""Native Aseprite filter/command wrappers (app.command.*).

These delegate to Aseprite's own engine filters instead of hand-rolling
pixel math in Lua — higher quality and faster than the equivalents in
fx.py. All verified to run headless under --batch (T0, 2026-06-18). They
are added ALONGSIDE the hand-rolled tools (outline_cel / adjust_hsl /
quantize_to_palette stay) per the "deprecate, don't break" policy.

General value (upstream-able): nothing Chimera-specific here.
"""
import json
import os

from ..core.commands import AsepriteCommand, lua_escape
from ..core.native import build_native_command_script
from .fx import _parse_hex_color
from .. import mcp

# Built-in convolution-matrix resource names (Aseprite data/convmatr.def).
CONVOLUTION_MATRICES = frozenset({
    "brightness", "contrast", "negative",
    "blur-3x3", "blur-3x3-hard", "blur-5x5", "blur-7x7", "blur-9x9", "blur-17x17",
    "blur-5x3-left", "blur-17x3-left", "blur-3x17-top",
    "blur-5x5-diagonal(\\)", "blur-5x5-diagonal(/)",
    "sharpen-3x3", "sharpen-5x5", "sharpen-7x7",
    "edges-find", "edges-find-horizontal", "edges-find-vertical",
    "misc-contour", "misc-texturize", "misc-emboss", "misc-marmolize",
    "misc-rock", "misc-rock-edges",
    "drunk-3x3_x", "drunk-3x3_+", "drunk-5x5_x", "drunk-5x5_+",
    "drunk-7x7_x", "drunk-7x7_+", "drunk-9x9_x", "drunk-9x9_+",
    "drunk-17x17_x", "drunk-17x17_+", "drunk-17x17_o",
    "outline-transparent-layer-(cross)", "outline-transparent-layer-(square)",
})


def _region(x: int, y: int, width: int, height: int):
    return (x, y, width, height) if width > 0 and height > 0 else None


@mcp.tool()
async def outline_native(
    filename: str,
    layer_name: str = "",
    frame_index: int = 1,
    color: str = "#000000",
    place: str = "outside",
    matrix: str = "circle",
) -> str:
    """Native Aseprite Outline around opaque pixels (app.command.Outline).

    Higher quality than the 1px hand-rolled outline_cel: inside/outside
    placement + a circle/square brush. Works best on a full-canvas cel.

    Args:
        filename: Aseprite file to modify
        layer_name: layer to outline (empty = active layer)
        frame_index: 1-based frame
        color: outline colour as #RRGGBB
        place: "outside" or "inside"
        matrix: "circle" or "square"
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    rgb = _parse_hex_color(color)
    if not rgb:
        return "Invalid color (expected #RRGGBB)"
    if place not in ("outside", "inside"):
        return "place must be 'outside' or 'inside'"
    if matrix not in ("circle", "square"):
        return "matrix must be 'circle' or 'square'"
    r, g, b = rgb
    cmd = (f'        app.command.Outline{{ui=false, color=Color{{r={r}, g={g}, '
           f'b={b}, a=255}}, place="{place}", matrix="{matrix}"}}')
    script = build_native_command_script(cmd, layer_name, frame_index)
    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return f"Outlined ({place}, {matrix}) {layer_name or 'active layer'} in {filename}"
    return f"Failed to outline: {output}"


@mcp.tool()
async def adjust_hsl_native(
    filename: str,
    layer_name: str = "",
    frame_index: int = 1,
    hue: int = 0,
    saturation: int = 0,
    lightness: int = 0,
    x: int = 0,
    y: int = 0,
    width: int = 0,
    height: int = 0,
) -> str:
    """Native Hue/Saturation/Lightness filter (engine-quality vs adjust_hsl).

    Args:
        filename: Aseprite file to modify
        layer_name: layer to adjust (empty = active layer)
        frame_index: 1-based frame
        hue: -180..180 (degrees)
        saturation: -100..100
        lightness: -100..100
        x, y, width, height: optional region (width>0 & height>0 to scope)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if not (-180 <= hue <= 180):
        return "hue must be -180..180"
    if not (-100 <= saturation <= 100) or not (-100 <= lightness <= 100):
        return "saturation and lightness must be -100..100"
    cmd = (f'        app.command.HueSaturation{{ui=false, hue={hue}, '
           f'saturation={saturation}, lightness={lightness}, alpha=0}}')
    script = build_native_command_script(cmd, layer_name, frame_index,
                                         _region(x, y, width, height))
    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return f"Adjusted HSL on {layer_name or 'active layer'} in {filename}"
    return f"Failed to adjust HSL: {output}"


@mcp.tool()
async def adjust_brightness_contrast(
    filename: str,
    layer_name: str = "",
    frame_index: int = 1,
    brightness: int = 0,
    contrast: int = 0,
    x: int = 0,
    y: int = 0,
    width: int = 0,
    height: int = 0,
) -> str:
    """Native Brightness/Contrast filter (app.command.BrightnessContrast).

    Args:
        filename: Aseprite file to modify
        layer_name: layer to adjust (empty = active layer)
        frame_index: 1-based frame
        brightness: -100..100
        contrast: -100..100
        x, y, width, height: optional region (width>0 & height>0 to scope)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if not (-100 <= brightness <= 100) or not (-100 <= contrast <= 100):
        return "brightness and contrast must be -100..100"
    cmd = (f'        app.command.BrightnessContrast{{ui=false, '
           f'brightness={brightness}, contrast={contrast}}}')
    script = build_native_command_script(cmd, layer_name, frame_index,
                                         _region(x, y, width, height))
    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return f"Adjusted brightness/contrast on {layer_name or 'active layer'} in {filename}"
    return f"Failed to adjust brightness/contrast: {output}"


@mcp.tool()
async def invert_colors(
    filename: str,
    layer_name: str = "",
    frame_index: int = 1,
    x: int = 0,
    y: int = 0,
    width: int = 0,
    height: int = 0,
) -> str:
    """Native colour inversion (app.command.InvertColor).

    Args:
        filename: Aseprite file to modify
        layer_name: layer to invert (empty = active layer)
        frame_index: 1-based frame
        x, y, width, height: optional region (width>0 & height>0 to scope)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    cmd = "        app.command.InvertColor{ui=false}"
    script = build_native_command_script(cmd, layer_name, frame_index,
                                         _region(x, y, width, height))
    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return f"Inverted colours on {layer_name or 'active layer'} in {filename}"
    return f"Failed to invert: {output}"


@mcp.tool()
async def apply_convolution(
    filename: str,
    matrix: str,
    layer_name: str = "",
    frame_index: int = 1,
    x: int = 0,
    y: int = 0,
    width: int = 0,
    height: int = 0,
) -> str:
    """Native convolution filter (blur / sharpen / edge / emboss …).

    Args:
        filename: Aseprite file to modify
        matrix: a built-in matrix name (see list_convolution_matrices),
            e.g. "blur-3x3", "sharpen-3x3", "edges-find", "misc-emboss"
        layer_name: layer to filter (empty = active layer)
        frame_index: 1-based frame
        x, y, width, height: optional region (width>0 & height>0 to scope)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if matrix not in CONVOLUTION_MATRICES:
        return (f"Unknown matrix {matrix!r}; call list_convolution_matrices for "
                f"the {len(CONVOLUTION_MATRICES)} valid names")
    cmd = f'        app.command.ConvolutionMatrix{{ui=false, fromResource="{lua_escape(matrix)}"}}'
    script = build_native_command_script(cmd, layer_name, frame_index,
                                         _region(x, y, width, height))
    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return f"Applied convolution '{matrix}' on {layer_name or 'active layer'} in {filename}"
    return f"Failed to apply convolution: {output}"


@mcp.tool()
async def list_convolution_matrices() -> str:
    """List the built-in convolution-matrix names usable with apply_convolution.

    Returns:
        JSON array of matrix resource names.
    """
    return json.dumps(sorted(CONVOLUTION_MATRICES))


@mcp.tool()
async def extract_palette(
    filename: str,
    max_colors: int = 16,
    with_alpha: bool = False,
) -> str:
    """Build an OPTIMAL palette from the sprite via native ColorQuantization.

    True palette extraction (vs the nearest-snap quantize_to_palette): writes
    the resulting palette to the sprite and returns it. NOTE: mutates the
    sprite's palette. Sprite must be in RGB mode.

    Args:
        filename: Aseprite file to modify
        max_colors: palette size cap, 1..256 (fewer if the art has fewer)
        with_alpha: include alpha when quantizing

    Returns:
        JSON {colors: [#RRGGBB, ...], count}
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if not (1 <= max_colors <= 256):
        return "max_colors must be 1..256"
    wa = "true" if with_alpha else "false"
    script = f"""
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end
    app.transaction(function()
        app.command.ColorQuantization{{ui=false, maxColors={max_colors}, withAlpha={wa}}}
    end)
    spr:saveAs(spr.filename)
    local pal = spr.palettes[1]
    for i = 0, #pal - 1 do
        local c = pal:getColor(i)
        print(string.format("PALETTE:#%02X%02X%02X", c.red, c.green, c.blue))
    end
    print("OK")
    """
    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if not success:
        return f"Failed to extract palette: {output}"
    colors = [ln[len("PALETTE:"):] for ln in output.splitlines() if ln.startswith("PALETTE:")]
    return json.dumps({"colors": colors, "count": len(colors)})
