import os
from typing import List, Dict, Any
from ..core.commands import AsepriteCommand, lua_escape
from .. import mcp


def _parse_hex_color(value: str) -> tuple[int, int, int] | None:
    if not value:
        return None
    hex_color = value.lstrip("#")
    if len(hex_color) != 6:
        return None
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    except ValueError:
        return None
    return r, g, b


@mcp.tool()
async def draw_pixels(filename: str, pixels: List[Dict[str, Any]]) -> str:
    """Draw pixels on the canvas with specified colors.

    Args:
        filename: Name of the Aseprite file to modify
        pixels: List of pixel data, each containing:
            {"x": int, "y": int, "color": str}
            where color is a hex code like "#FF0000"
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    script = """
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    app.transaction(function()
        local cel = app.activeCel
        if not cel then
            -- If no active cel, create one
            app.activeLayer = spr.layers[1]
            app.activeFrame = spr.frames[1]
            cel = app.activeCel
            if not cel then
                return "No active cel and couldn't create one"
            end
        end

        local img = cel.image
    """

    # Add pixel drawing commands
    for pixel in pixels:
        x = pixel.get("x", 0)
        y = pixel.get("y", 0)
        rgb = _parse_hex_color(pixel.get("color", "#000000"))
        if rgb is None:
            return f"Invalid color value: {pixel.get('color')}"
        r, g, b = rgb

        script += f"""
        img:putPixel({x}, {y}, Color({r}, {g}, {b}, 255))
        """

    script += """
    end)

    spr:saveAs(spr.filename)
    return "Pixels drawn successfully"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)

    if success:
        return f"Pixels drawn successfully in {filename}"
    else:
        return f"Failed to draw pixels: {output}"

@mcp.tool()
async def draw_line(filename: str, x1: int, y1: int, x2: int, y2: int, color: str = "#000000", thickness: int = 1) -> str:
    """Draw a line on the canvas.

    Args:
        filename: Name of the Aseprite file to modify
        x1: Starting x coordinate
        y1: Starting y coordinate
        x2: Ending x coordinate
        y2: Ending y coordinate
        color: Hex color code (default: "#000000")
        thickness: Line thickness in pixels (default: 1)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    rgb = _parse_hex_color(color)
    if rgb is None:
        return f"Invalid color value: {color}"
    r, g, b = rgb

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local function put_thick(img, x, y, color, size)
        local r = math.max(0, math.floor(size / 2))
        for oy = -r, r do
            for ox = -r, r do
                img:putPixel(x + ox, y + oy, color)
            end
        end
    end

    local function draw_line(img, x0, y0, x1, y1, color, size)
        local dx = math.abs(x1 - x0)
        local sx = x0 < x1 and 1 or -1
        local dy = -math.abs(y1 - y0)
        local sy = y0 < y1 and 1 or -1
        local err = dx + dy
        while true do
            if size > 1 then
                put_thick(img, x0, y0, color, size)
            else
                img:putPixel(x0, y0, color)
            end
            if x0 == x1 and y0 == y1 then break end
            local e2 = 2 * err
            if e2 >= dy then err = err + dy; x0 = x0 + sx end
            if e2 <= dx then err = err + dx; y0 = y0 + sy end
        end
    end

    app.transaction(function()
        local cel = app.activeCel
        if not cel then
            app.activeLayer = spr.layers[1]
            app.activeFrame = spr.frames[1]
            cel = app.activeCel
            if not cel then
                return "No active cel and couldn't create one"
            end
        end
        local img = cel.image
        local color = Color({r}, {g}, {b}, 255)
        draw_line(img, {x1}, {y1}, {x2}, {y2}, color, {thickness})
    end)

    spr:saveAs(spr.filename)
    return "Line drawn successfully"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)

    if success:
        return f"Line drawn successfully in {filename}"
    else:
        return f"Failed to draw line: {output}"

@mcp.tool()
async def draw_rectangle(filename: str, x: int, y: int, width: int, height: int, color: str = "#000000", fill: bool = False) -> str:
    """Draw a rectangle on the canvas.

    Args:
        filename: Name of the Aseprite file to modify
        x: Top-left x coordinate
        y: Top-left y coordinate
        width: Width of the rectangle in pixels (must be > 0)
        height: Height of the rectangle in pixels (must be > 0)
        color: Hex color code (default: "#000000")
        fill: Whether to fill the rectangle (default: False)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if width <= 0 or height <= 0:
        return "Width and height must be > 0"

    rgb = _parse_hex_color(color)
    if rgb is None:
        return f"Invalid color value: {color}"
    r, g, b = rgb

    # app.useTool treats both points as inclusive corners, so the second
    # point sits at (x+width-1, y+height-1) for a width x height rect.
    x2 = x + width - 1
    y2 = y + height - 1

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    app.transaction(function()
        local cel = app.activeCel
        if not cel then
            app.activeLayer = spr.layers[1]
            app.activeFrame = spr.frames[1]
            cel = app.activeCel
            if not cel then
                return "No active cel and couldn't create one"
            end
        end

        local color = Color({r}, {g}, {b}, 255)
        local tool = {'"rectangle"' if not fill else '"filled_rectangle"'}
        app.useTool({{
            tool=tool,
            color=color,
            points={{Point({x}, {y}), Point({x2}, {y2})}}
        }})
    end)

    spr:saveAs(spr.filename)
    return "Rectangle drawn successfully"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)

    if success:
        return f"Rectangle drawn successfully in {filename}"
    else:
        return f"Failed to draw rectangle: {output}"

@mcp.tool()
async def fill_area(filename: str, x: int, y: int, color: str = "#000000") -> str:
    """Fill an area with color using the paint bucket tool.

    Args:
        filename: Name of the Aseprite file to modify
        x: X coordinate to fill from
        y: Y coordinate to fill from
        color: Hex color code (default: "#000000")
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    rgb = _parse_hex_color(color)
    if rgb is None:
        return f"Invalid color value: {color}"
    r, g, b = rgb

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    app.transaction(function()
        local cel = app.activeCel
        if not cel then
            app.activeLayer = spr.layers[1]
            app.activeFrame = spr.frames[1]
            cel = app.activeCel
            if not cel then
                return "No active cel and couldn't create one"
            end
        end

        local color = Color({r}, {g}, {b}, 255)
        app.useTool({{
            tool="paint_bucket",
            color=color,
            points={{Point({x}, {y})}}
        }})
    end)

    spr:saveAs(spr.filename)
    return "Area filled successfully"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)

    if success:
        return f"Area filled successfully in {filename}"
    else:
        return f"Failed to fill area: {output}"

@mcp.tool()
async def draw_circle(filename: str, center_x: int, center_y: int, radius: int, color: str = "#000000", fill: bool = False) -> str:
    """Draw a circle on the canvas.

    Args:
        filename: Name of the Aseprite file to modify
        center_x: X coordinate of circle center
        center_y: Y coordinate of circle center
        radius: Radius of the circle in pixels
        color: Hex color code (default: "#000000")
        fill: Whether to fill the circle (default: False)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    rgb = _parse_hex_color(color)
    if rgb is None:
        return f"Invalid color value: {color}"
    r, g, b = rgb

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    app.transaction(function()
        local cel = app.activeCel
        if not cel then
            app.activeLayer = spr.layers[1]
            app.activeFrame = spr.frames[1]
            cel = app.activeCel
            if not cel then
                return "No active cel and couldn't create one"
            end
        end

        local color = Color({r}, {g}, {b}, 255)
        local tool = {'"ellipse"' if not fill else '"filled_ellipse"'}
        app.useTool({{
            tool=tool,
            color=color,
            points={{
                Point({center_x - radius}, {center_y - radius}),
                Point({center_x + radius}, {center_y + radius})
            }}
        }})
    end)

    spr:saveAs(spr.filename)
    return "Circle drawn successfully"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)

    if success:
        return f"Circle drawn successfully in {filename}"
    else:
        return f"Failed to draw circle: {output}"

@mcp.tool()
async def draw_pixels_at(
    filename: str,
    layer_name: str,
    frame_index: int,
    pixels: List[Dict[str, Any]],
    create_if_missing: bool = True
) -> str:
    """Draw pixels on a specific layer/frame.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        frame_index: Frame index starting at 1
        pixels: List of pixel data with x/y/color
        create_if_missing: Create cel if it does not exist
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    safe_layer_name = lua_escape(layer_name)
    create_flag = "true" if create_if_missing else "false"
    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then return "Frame index out of range" end

    local target = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{safe_layer_name}" then target = layer break end
    end
    if not target then return "Layer not found" end

    app.transaction(function()
        app.activeLayer = target
        app.activeFrame = spr.frames[idx]
        local cel = target:cel(spr.frames[idx])
        if not cel and {create_flag} then
            local img = Image(spr.width, spr.height, spr.colorMode)
            cel = spr:newCel(target, spr.frames[idx], img, Point(0, 0))
        end
        if not cel then return end
        local img = cel.image
    """
    for pixel in pixels:
        x = pixel.get("x", 0)
        y = pixel.get("y", 0)
        rgb = _parse_hex_color(pixel.get("color", "#000000"))
        if rgb is None:
            return f"Invalid color value: {pixel.get('color')}"
        r, g, b = rgb
        script += f"""
        img:putPixel({x}, {y}, Color({r}, {g}, {b}, 255))
        """

    script += """
    end)

    spr:saveAs(spr.filename)
    return "Pixels drawn"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Pixels drawn on '{layer_name}' frame {frame_index} in {filename}"
    return f"Failed to draw pixels: {output}"

@mcp.tool()
async def draw_line_at(
    filename: str,
    layer_name: str,
    frame_index: int,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: str = "#000000",
    thickness: int = 1,
    create_if_missing: bool = True
) -> str:
    """Draw a line on a specific layer/frame."""
    if not os.path.exists(filename):
        return f"File {filename} not found"

    rgb = _parse_hex_color(color)
    if rgb is None:
        return f"Invalid color value: {color}"
    r, g, b = rgb
    safe_layer_name = lua_escape(layer_name)
    create_flag = "true" if create_if_missing else "false"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local function put_thick(img, x, y, color, size)
        local r = math.max(0, math.floor(size / 2))
        for oy = -r, r do
            for ox = -r, r do
                img:putPixel(x + ox, y + oy, color)
            end
        end
    end

    local function draw_line(img, x0, y0, x1, y1, color, size)
        local dx = math.abs(x1 - x0)
        local sx = x0 < x1 and 1 or -1
        local dy = -math.abs(y1 - y0)
        local sy = y0 < y1 and 1 or -1
        local err = dx + dy
        while true do
            if size > 1 then
                put_thick(img, x0, y0, color, size)
            else
                img:putPixel(x0, y0, color)
            end
            if x0 == x1 and y0 == y1 then break end
            local e2 = 2 * err
            if e2 >= dy then err = err + dy; x0 = x0 + sx end
            if e2 <= dx then err = err + dx; y0 = y0 + sy end
        end
    end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then return "Frame index out of range" end

    local target = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{safe_layer_name}" then target = layer break end
    end
    if not target then return "Layer not found" end

    app.transaction(function()
        app.activeLayer = target
        app.activeFrame = spr.frames[idx]
        local cel = target:cel(spr.frames[idx])
        if not cel and {create_flag} then
            local img = Image(spr.width, spr.height, spr.colorMode)
            cel = spr:newCel(target, spr.frames[idx], img, Point(0, 0))
        end
        if not cel then return end
        local img = cel.image
        local color = Color({r}, {g}, {b}, 255)
        draw_line(img, {x1}, {y1}, {x2}, {y2}, color, {thickness})
    end)

    spr:saveAs(spr.filename)
    return "Line drawn"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Line drawn on '{layer_name}' frame {frame_index} in {filename}"
    return f"Failed to draw line: {output}"

@mcp.tool()
async def draw_rectangle_at(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int,
    y: int,
    width: int,
    height: int,
    color: str = "#000000",
    fill: bool = False,
    create_if_missing: bool = True
) -> str:
    """Draw a rectangle on a specific layer/frame."""
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if width <= 0 or height <= 0:
        return "Width and height must be > 0"

    rgb = _parse_hex_color(color)
    if rgb is None:
        return f"Invalid color value: {color}"
    r, g, b = rgb
    safe_layer_name = lua_escape(layer_name)
    create_flag = "true" if create_if_missing else "false"
    x2 = x + width - 1
    y2 = y + height - 1

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then return "Frame index out of range" end

    local target = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{safe_layer_name}" then target = layer break end
    end
    if not target then return "Layer not found" end

    app.transaction(function()
        app.activeLayer = target
        app.activeFrame = spr.frames[idx]
        local cel = target:cel(spr.frames[idx])
        if not cel and {create_flag} then
            local img = Image(spr.width, spr.height, spr.colorMode)
            cel = spr:newCel(target, spr.frames[idx], img, Point(0, 0))
        end
        if not cel then return end
        local color = Color({r}, {g}, {b}, 255)
        local tool = {'"rectangle"' if not fill else '"filled_rectangle"'}
        app.useTool({{
            tool=tool,
            color=color,
            points={{Point({x}, {y}), Point({x2}, {y2})}}
        }})
    end)

    spr:saveAs(spr.filename)
    return "Rectangle drawn"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Rectangle drawn on '{layer_name}' frame {frame_index} in {filename}"
    return f"Failed to draw rectangle: {output}"

@mcp.tool()
async def draw_circle_at(
    filename: str,
    layer_name: str,
    frame_index: int,
    center_x: int,
    center_y: int,
    radius: int,
    color: str = "#000000",
    fill: bool = False,
    create_if_missing: bool = True
) -> str:
    """Draw a circle on a specific layer/frame."""
    if not os.path.exists(filename):
        return f"File {filename} not found"

    rgb = _parse_hex_color(color)
    if rgb is None:
        return f"Invalid color value: {color}"
    r, g, b = rgb
    safe_layer_name = lua_escape(layer_name)
    create_flag = "true" if create_if_missing else "false"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then return "Frame index out of range" end

    local target = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{safe_layer_name}" then target = layer break end
    end
    if not target then return "Layer not found" end

    app.transaction(function()
        app.activeLayer = target
        app.activeFrame = spr.frames[idx]
        local cel = target:cel(spr.frames[idx])
        if not cel and {create_flag} then
            local img = Image(spr.width, spr.height, spr.colorMode)
            cel = spr:newCel(target, spr.frames[idx], img, Point(0, 0))
        end
        if not cel then return end
        local color = Color({r}, {g}, {b}, 255)
        local tool = {'"ellipse"' if not fill else '"filled_ellipse"'}
        app.useTool({{
            tool=tool,
            color=color,
            points={{
                Point({center_x - radius}, {center_y - radius}),
                Point({center_x + radius}, {center_y + radius})
            }}
        }})
    end)

    spr:saveAs(spr.filename)
    return "Circle drawn"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Circle drawn on '{layer_name}' frame {frame_index} in {filename}"
    return f"Failed to draw circle: {output}"

@mcp.tool()
async def fill_area_at(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int,
    y: int,
    color: str = "#000000",
    create_if_missing: bool = True
) -> str:
    """Fill an area on a specific layer/frame."""
    if not os.path.exists(filename):
        return f"File {filename} not found"

    rgb = _parse_hex_color(color)
    if rgb is None:
        return f"Invalid color value: {color}"
    r, g, b = rgb
    safe_layer_name = lua_escape(layer_name)
    create_flag = "true" if create_if_missing else "false"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then return "Frame index out of range" end

    local target = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{safe_layer_name}" then target = layer break end
    end
    if not target then return "Layer not found" end

    app.transaction(function()
        app.activeLayer = target
        app.activeFrame = spr.frames[idx]
        local cel = target:cel(spr.frames[idx])
        if not cel and {create_flag} then
            local img = Image(spr.width, spr.height, spr.colorMode)
            cel = spr:newCel(target, spr.frames[idx], img, Point(0, 0))
        end
        if not cel then return end
        local color = Color({r}, {g}, {b}, 255)
        app.useTool({{
            tool="paint_bucket",
            color=color,
            points={{Point({x}, {y})}}
        }})
    end)

    spr:saveAs(spr.filename)
    return "Area filled"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Area filled on '{layer_name}' frame {frame_index} in {filename}"
    return f"Failed to fill area: {output}"

@mcp.tool()
async def draw_polygon(
    filename: str,
    layer_name: str,
    frame_index: int,
    points: List[Dict[str, int]],
    color: str = "#000000",
    fill: bool = False,
    create_if_missing: bool = True
) -> str:
    """Draw a polygon on a specific layer/frame."""
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if len(points) < 3:
        return "Polygon requires at least 3 points"

    rgb = _parse_hex_color(color)
    if rgb is None:
        return f"Invalid color value: {color}"
    r, g, b = rgb
    safe_layer_name = lua_escape(layer_name)
    create_flag = "true" if create_if_missing else "false"
    fill_flag = "true" if fill else "false"
    points_lua = ", ".join([f"{{x={p['x']}, y={p['y']}}}" for p in points])

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local function put_thick(img, x, y, color, size)
        local r = math.max(0, math.floor(size / 2))
        for oy = -r, r do
            for ox = -r, r do
                img:putPixel(x + ox, y + oy, color)
            end
        end
    end

    local function draw_line(img, x0, y0, x1, y1, color)
        local dx = math.abs(x1 - x0)
        local sx = x0 < x1 and 1 or -1
        local dy = -math.abs(y1 - y0)
        local sy = y0 < y1 and 1 or -1
        local err = dx + dy
        while true do
            img:putPixel(x0, y0, color)
            if x0 == x1 and y0 == y1 then break end
            local e2 = 2 * err
            if e2 >= dy then err = err + dy; x0 = x0 + sx end
            if e2 <= dx then err = err + dx; y0 = y0 + sy end
        end
    end

    local function fill_polygon(img, pts, color)
        local minY = pts[1].y
        local maxY = pts[1].y
        for i = 2, #pts do
            if pts[i].y < minY then minY = pts[i].y end
            if pts[i].y > maxY then maxY = pts[i].y end
        end
        for y = minY, maxY do
            local nodes = {{}}
            local j = #pts
            for i = 1, #pts do
                local xi, yi = pts[i].x, pts[i].y
                local xj, yj = pts[j].x, pts[j].y
                if (yi < y and yj >= y) or (yj < y and yi >= y) then
                    local x = xi + (y - yi) * (xj - xi) / (yj - yi)
                    table.insert(nodes, x)
                end
                j = i
            end
            table.sort(nodes)
            for k = 1, #nodes, 2 do
                if nodes[k + 1] ~= nil then
                    local x_start = math.floor(nodes[k] + 0.5)
                    local x_end = math.floor(nodes[k + 1] + 0.5)
                    for x = x_start, x_end do
                        img:putPixel(x, y, color)
                    end
                end
            end
        end
    end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then return "Frame index out of range" end

    local target = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{safe_layer_name}" then target = layer break end
    end
    if not target then return "Layer not found" end

    app.transaction(function()
        app.activeLayer = target
        app.activeFrame = spr.frames[idx]
        local cel = target:cel(spr.frames[idx])
        if not cel and {create_flag} then
            local img = Image(spr.width, spr.height, spr.colorMode)
            cel = spr:newCel(target, spr.frames[idx], img, Point(0, 0))
        end
        if not cel then return end
        local img = cel.image
        local color = Color({r}, {g}, {b}, 255)
        local pts = {{ {points_lua} }}
        if {fill_flag} then
            fill_polygon(img, pts, color)
        end
        for i = 1, #pts do
            local n = i + 1
            if n > #pts then n = 1 end
            draw_line(img, pts[i].x, pts[i].y, pts[n].x, pts[n].y, color)
        end
    end)

    spr:saveAs(spr.filename)
    return "Polygon drawn"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Polygon drawn on '{layer_name}' frame {frame_index} in {filename}"
    return f"Failed to draw polygon: {output}"

@mcp.tool()
async def draw_path(
    filename: str,
    layer_name: str,
    frame_index: int,
    points: List[Dict[str, int]],
    color: str = "#000000",
    thickness: int = 1,
    create_if_missing: bool = True
) -> str:
    """Draw a path using a polyline on a specific layer/frame."""
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if len(points) < 2:
        return "Path requires at least 2 points"

    rgb = _parse_hex_color(color)
    if rgb is None:
        return f"Invalid color value: {color}"
    r, g, b = rgb
    safe_layer_name = lua_escape(layer_name)
    create_flag = "true" if create_if_missing else "false"
    points_lua = ", ".join([f"{{x={p['x']}, y={p['y']}}}" for p in points])

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local function put_thick(img, x, y, color, size)
        local r = math.max(0, math.floor(size / 2))
        for oy = -r, r do
            for ox = -r, r do
                img:putPixel(x + ox, y + oy, color)
            end
        end
    end

    local function draw_line(img, x0, y0, x1, y1, color, size)
        local dx = math.abs(x1 - x0)
        local sx = x0 < x1 and 1 or -1
        local dy = -math.abs(y1 - y0)
        local sy = y0 < y1 and 1 or -1
        local err = dx + dy
        while true do
            if size > 1 then
                put_thick(img, x0, y0, color, size)
            else
                img:putPixel(x0, y0, color)
            end
            if x0 == x1 and y0 == y1 then break end
            local e2 = 2 * err
            if e2 >= dy then err = err + dy; x0 = x0 + sx end
            if e2 <= dx then err = err + dx; y0 = y0 + sy end
        end
    end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then return "Frame index out of range" end

    local target = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{safe_layer_name}" then target = layer break end
    end
    if not target then return "Layer not found" end

    app.transaction(function()
        app.activeLayer = target
        app.activeFrame = spr.frames[idx]
        local cel = target:cel(spr.frames[idx])
        if not cel and {create_flag} then
            local img = Image(spr.width, spr.height, spr.colorMode)
            cel = spr:newCel(target, spr.frames[idx], img, Point(0, 0))
        end
        if not cel then return end
        local img = cel.image
        local color = Color({r}, {g}, {b}, 255)
        local pts = {{ {points_lua} }}
        for i = 1, #pts - 1 do
            draw_line(img, pts[i].x, pts[i].y, pts[i + 1].x, pts[i + 1].y, color, {thickness})
        end
    end)

    spr:saveAs(spr.filename)
    return "Path drawn"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Path drawn on '{layer_name}' frame {frame_index} in {filename}"
    return f"Failed to draw path: {output}"

@mcp.tool()
async def apply_gradient_rect(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int,
    y: int,
    width: int,
    height: int,
    color_start: str,
    color_end: str,
    horizontal: bool = True,
    create_if_missing: bool = True
) -> str:
    """Apply a linear gradient fill to a rectangle."""
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if width <= 0 or height <= 0:
        return "Width and height must be > 0"

    start_rgb = _parse_hex_color(color_start)
    if start_rgb is None:
        return f"Invalid color_start value: {color_start}"
    end_rgb = _parse_hex_color(color_end)
    if end_rgb is None:
        return f"Invalid color_end value: {color_end}"

    sr, sg, sb = start_rgb
    er, eg, eb = end_rgb
    safe_layer_name = lua_escape(layer_name)
    create_flag = "true" if create_if_missing else "false"
    horiz_flag = "true" if horizontal else "false"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then return "Frame index out of range" end

    local target = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{safe_layer_name}" then target = layer break end
    end
    if not target then return "Layer not found" end

    app.transaction(function()
        app.activeLayer = target
        app.activeFrame = spr.frames[idx]
        local cel = target:cel(spr.frames[idx])
        if not cel and {create_flag} then
            local img = Image(spr.width, spr.height, spr.colorMode)
            cel = spr:newCel(target, spr.frames[idx], img, Point(0, 0))
        end
        if not cel then return end
        local img = cel.image
        local w = {width}
        local h = {height}
        for iy = 0, h - 1 do
            for ix = 0, w - 1 do
                local t = 0
                if {horiz_flag} then
                    t = (w > 1) and (ix / (w - 1)) or 0
                else
                    t = (h > 1) and (iy / (h - 1)) or 0
                end
                local r = math.floor({sr} + ({er} - {sr}) * t + 0.5)
                local g = math.floor({sg} + ({eg} - {sg}) * t + 0.5)
                local b = math.floor({sb} + ({eb} - {sb}) * t + 0.5)
                img:putPixel({x} + ix, {y} + iy, Color(r, g, b, 255))
            end
        end
    end)

    spr:saveAs(spr.filename)
    return "Gradient applied"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Gradient applied on '{layer_name}' frame {frame_index} in {filename}"
    return f"Failed to apply gradient: {output}"
