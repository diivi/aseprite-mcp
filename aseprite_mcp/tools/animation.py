import os
import json
from ..core.commands import AsepriteCommand
from .. import mcp

@mcp.tool()
async def add_frames(filename: str, count: int, duration_ms: int | None = None) -> str:
    """Add multiple frames to a sprite and optionally set their duration.

    Args:
        filename: Name of the Aseprite file to modify
        count: Number of frames to add
        duration_ms: Optional duration for each new frame in milliseconds
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    if count < 1:
        return "Count must be >= 1"

    duration_line = ""
    if duration_ms is not None and duration_ms > 0:
        duration_line = f"spr.frames[#spr.frames].duration = {duration_ms} / 1000.0"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    app.transaction(function()
        for i = 1, {count} do
            spr:newFrame()
            {duration_line}
        end
    end)

    spr:saveAs(spr.filename)
    return "Frames added"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Added {count} frames to {filename}"
    return f"Failed to add frames: {output}"

@mcp.tool()
async def set_frame_duration_all(filename: str, duration_ms: int) -> str:
    """Set the duration of all frames in milliseconds.

    Args:
        filename: Name of the Aseprite file to modify
        duration_ms: Duration in milliseconds
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if duration_ms <= 0:
        return "Duration must be > 0"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    app.transaction(function()
        for i = 1, #spr.frames do
            spr.frames[i].duration = {duration_ms} / 1000.0
        end
    end)

    spr:saveAs(spr.filename)
    return "Frame durations set"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Set duration of all frames to {duration_ms}ms in {filename}"
    return f"Failed to set frame durations: {output}"

@mcp.tool()
async def set_layer_visibility(filename: str, layer_name: str, visible: bool = True) -> str:
    """Set layer visibility by name.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        visible: Whether the layer should be visible
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    visible_flag = "true" if visible else "false"
    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local target = nil
    for i, layer in ipairs(spr.layers) do
        if layer.name == "{layer_name}" then
            target = layer
            break
        end
    end
    if not target then return "Layer not found" end

    app.transaction(function()
        target.isVisible = {visible_flag}
    end)

    spr:saveAs(spr.filename)
    return "Layer visibility set"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Layer '{layer_name}' visibility set to {visible} in {filename}"
    return f"Failed to set layer visibility: {output}"

@mcp.tool()
async def set_layer_opacity(filename: str, layer_name: str, opacity: int) -> str:
    """Set layer opacity by name (0-255).

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        opacity: Opacity value 0-255
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if opacity < 0 or opacity > 255:
        return "Opacity must be between 0 and 255"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local target = nil
    for i, layer in ipairs(spr.layers) do
        if layer.name == "{layer_name}" then
            target = layer
            break
        end
    end
    if not target then return "Layer not found" end

    app.transaction(function()
        target.opacity = {opacity}
    end)

    spr:saveAs(spr.filename)
    return "Layer opacity set"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Layer '{layer_name}' opacity set to {opacity} in {filename}"
    return f"Failed to set layer opacity: {output}"

@mcp.tool()
async def get_sprite_info(filename: str) -> str:
    """Return sprite info as JSON string (size, frame count, layers).

    Args:
        filename: Name of the Aseprite file to inspect
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    script = """
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local parts = {}
    table.insert(parts, "{")
    table.insert(parts, "\\"width\\":" .. spr.width .. ",")
    table.insert(parts, "\\"height\\":" .. spr.height .. ",")
    table.insert(parts, "\\"frames\\":" .. #spr.frames .. ",")
    table.insert(parts, "\\"layers\\":[")
    for i, layer in ipairs(spr.layers) do
        local entry = "{\\"name\\":\\"" .. layer.name .. "\\",\\"visible\\":" .. tostring(layer.isVisible) .. ",\\"opacity\\":" .. layer.opacity .. "}"
        table.insert(parts, entry)
        if i < #spr.layers then
            table.insert(parts, ",")
        end
    end
    table.insert(parts, "]}")
    return table.concat(parts)
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return output
    return f"Failed to get sprite info: {output}"
