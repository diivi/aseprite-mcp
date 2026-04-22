import json
import os
from ..core.commands import AsepriteCommand, lua_escape
from .. import mcp


@mcp.tool()
async def get_pixel_color(
    filename: str,
    x: int,
    y: int,
    layer_name: str = "",
    frame_index: int = 1,
) -> str:
    """Read the RGBA color of a single pixel.

    Args:
        filename: Aseprite file to read
        x: X coordinate
        y: Y coordinate
        layer_name: Layer to read from (uses active layer when empty)
        frame_index: Frame index starting at 1
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    safe_layer = lua_escape(layer_name)
    script = f"""
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then print("ERROR:Frame index out of range") return end

    local img = nil
    if "{safe_layer}" ~= "" then
        local target = nil
        for _, layer in ipairs(spr.layers) do
            if layer.name == "{safe_layer}" then target = layer break end
        end
        if not target then print("ERROR:Layer not found") return end
        local cel = target:cel(spr.frames[idx])
        if not cel then print("ERROR:No cel at that layer/frame") return end
        img = cel.image
    else
        app.activeFrame = spr.frames[idx]
        local cel = app.activeCel
        if not cel then print("ERROR:No active cel") return end
        img = cel.image
    end

    local px_val = img:getPixel({x}, {y})
    local r = app.pixelColor.rgbaR(px_val)
    local g = app.pixelColor.rgbaG(px_val)
    local b = app.pixelColor.rgbaB(px_val)
    local a = app.pixelColor.rgbaA(px_val)
    print(string.format("PIXEL:%d,%d,%d,%d", r, g, b, a))
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if not success:
        return f"Failed to read pixel: {output}"

    for line in output.splitlines():
        if line.startswith("ERROR:"):
            return line[6:]
        if line.startswith("PIXEL:"):
            parts = line[6:].split(",")
            r, g, b, a = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
            return f"#{r:02x}{g:02x}{b:02x} (r={r}, g={g}, b={b}, a={a})"

    return "No pixel data returned"


@mcp.tool()
async def get_pixels_rect(
    filename: str,
    x: int,
    y: int,
    width: int,
    height: int,
    layer_name: str = "",
    frame_index: int = 1,
) -> str:
    """Read all pixel colors in a rectangular region.

    Args:
        filename: Aseprite file to read
        x: Top-left x coordinate
        y: Top-left y coordinate
        width: Width of the region
        height: Height of the region
        layer_name: Layer to read from (uses active layer when empty)
        frame_index: Frame index starting at 1

    Returns:
        JSON array of {x, y, hex, r, g, b, a} objects
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if width <= 0 or height <= 0:
        return "Width and height must be > 0"

    safe_layer = lua_escape(layer_name)
    x_end = x + width - 1
    y_end = y + height - 1

    script = f"""
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then print("ERROR:Frame index out of range") return end

    local img = nil
    if "{safe_layer}" ~= "" then
        local target = nil
        for _, layer in ipairs(spr.layers) do
            if layer.name == "{safe_layer}" then target = layer break end
        end
        if not target then print("ERROR:Layer not found") return end
        local cel = target:cel(spr.frames[idx])
        if not cel then print("ERROR:No cel at that layer/frame") return end
        img = cel.image
    else
        app.activeFrame = spr.frames[idx]
        local cel = app.activeCel
        if not cel then print("ERROR:No active cel") return end
        img = cel.image
    end

    for py = {y}, {y_end} do
        for px = {x}, {x_end} do
            local px_val = img:getPixel(px, py)
            local r = app.pixelColor.rgbaR(px_val)
            local g = app.pixelColor.rgbaG(px_val)
            local b = app.pixelColor.rgbaB(px_val)
            local a = app.pixelColor.rgbaA(px_val)
            print(string.format("PIXEL:%d,%d,%d,%d,%d,%d", px, py, r, g, b, a))
        end
    end
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if not success:
        return f"Failed to read pixels: {output}"

    pixels = []
    for line in output.splitlines():
        if line.startswith("ERROR:"):
            return line[6:]
        if line.startswith("PIXEL:"):
            parts = line[6:].split(",")
            px, py, r, g, b, a = [int(p) for p in parts]
            pixels.append({
                "x": px, "y": py,
                "hex": f"#{r:02x}{g:02x}{b:02x}",
                "r": r, "g": g, "b": b, "a": a,
            })

    if not pixels:
        return "No pixel data returned"
    return json.dumps(pixels)
