import os
from ..core.commands import AsepriteCommand, lua_escape
from .. import mcp


@mcp.tool()
async def flip_layer(
    filename: str,
    layer_name: str,
    frame_index: int,
    direction: str = "horizontal",
) -> str:
    """Flip a layer's image horizontally or vertically.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer name to flip
        frame_index: Frame index starting at 1
        direction: "horizontal" or "vertical"
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if direction not in ("horizontal", "vertical"):
        return "direction must be 'horizontal' or 'vertical'"

    safe_layer = lua_escape(layer_name)
    flip_h = "true" if direction == "horizontal" else "false"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then return "Frame index out of range" end

    local target = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{safe_layer}" then target = layer break end
    end
    if not target then return "Layer not found" end

    local cel = target:cel(spr.frames[idx])
    if not cel then return "No cel at that layer/frame" end

    app.transaction(function()
        local img = cel.image
        local w = img.width
        local h = img.height
        local flip_horizontal = {flip_h}

        local pixels = {{}}
        for py = 0, h - 1 do
            pixels[py] = {{}}
            for px = 0, w - 1 do
                pixels[py][px] = img:getPixel(px, py)
            end
        end

        for py = 0, h - 1 do
            for px = 0, w - 1 do
                if flip_horizontal then
                    img:putPixel(px, py, pixels[py][w - 1 - px])
                else
                    img:putPixel(px, py, pixels[h - 1 - py][px])
                end
            end
        end
    end)

    spr:saveAs(spr.filename)
    return "Layer flipped"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Layer '{layer_name}' flipped {direction}ly in {filename}"
    return f"Failed to flip layer: {output}"


@mcp.tool()
async def rotate_layer(
    filename: str,
    layer_name: str,
    frame_index: int,
    angle: int = 90,
) -> str:
    """Rotate a layer's image 90, 180, or 270 degrees clockwise.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer name to rotate
        frame_index: Frame index starting at 1
        angle: Rotation angle: 90, 180, or 270 (clockwise)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if angle not in (90, 180, 270):
        return "angle must be 90, 180, or 270"

    safe_layer = lua_escape(layer_name)

    if angle == 180:
        rotate_lua = """
        local w = img.width
        local h = img.height
        local pixels = {}
        for py = 0, h - 1 do
            pixels[py] = {}
            for px = 0, w - 1 do
                pixels[py][px] = img:getPixel(px, py)
            end
        end
        for py = 0, h - 1 do
            for px = 0, w - 1 do
                img:putPixel(px, py, pixels[h - 1 - py][w - 1 - px])
            end
        end
        """
    elif angle == 90:
        # 90° clockwise: (px, py) → (old_h-1-py, px) in new image (new_w=old_h, new_h=old_w)
        rotate_lua = """
        local old_w = img.width
        local old_h = img.height
        local new_img = Image(old_h, old_w, img.colorMode)
        for py = 0, old_h - 1 do
            for px = 0, old_w - 1 do
                new_img:putPixel(old_h - 1 - py, px, img:getPixel(px, py))
            end
        end
        cel.image = new_img
        """
    else:
        # 270° clockwise (= 90° CCW): (px, py) → (py, old_w-1-px) in new image (new_w=old_h, new_h=old_w)
        rotate_lua = """
        local old_w = img.width
        local old_h = img.height
        local new_img = Image(old_h, old_w, img.colorMode)
        for py = 0, old_h - 1 do
            for px = 0, old_w - 1 do
                new_img:putPixel(py, old_w - 1 - px, img:getPixel(px, py))
            end
        end
        cel.image = new_img
        """

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then return "Frame index out of range" end

    local target = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{safe_layer}" then target = layer break end
    end
    if not target then return "Layer not found" end

    local cel = target:cel(spr.frames[idx])
    if not cel then return "No cel at that layer/frame" end

    app.transaction(function()
        local img = cel.image
        {rotate_lua}
    end)

    spr:saveAs(spr.filename)
    return "Layer rotated"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Layer '{layer_name}' rotated {angle}° clockwise in {filename}"
    return f"Failed to rotate layer: {output}"


@mcp.tool()
async def resize_canvas(filename: str, width: int, height: int) -> str:
    """Scale the canvas and all its content to new dimensions.

    Args:
        filename: Aseprite file to modify
        width: New canvas width in pixels
        height: New canvas height in pixels
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if width <= 0 or height <= 0:
        return "Width and height must be > 0"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    app.transaction(function()
        spr:resize({width}, {height})
    end)

    spr:saveAs(spr.filename)
    return "Canvas resized"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Canvas resized to {width}x{height} in {filename}"
    return f"Failed to resize canvas: {output}"


@mcp.tool()
async def crop_canvas(filename: str, x: int, y: int, width: int, height: int) -> str:
    """Crop the canvas to the given rectangle, discarding content outside it.

    Args:
        filename: Aseprite file to modify
        x: Left edge of the crop area
        y: Top edge of the crop area
        width: Width of the crop area
        height: Height of the crop area
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if width <= 0 or height <= 0:
        return "Width and height must be > 0"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    app.transaction(function()
        spr:crop({x}, {y}, {width}, {height})
    end)

    spr:saveAs(spr.filename)
    return "Canvas cropped"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Canvas cropped to ({x},{y}) {width}x{height} in {filename}"
    return f"Failed to crop canvas: {output}"
