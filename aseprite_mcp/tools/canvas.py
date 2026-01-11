import os
from ..core.commands import AsepriteCommand
from .. import mcp

@mcp.tool()
async def create_canvas(width: int, height: int, filename: str = "canvas.aseprite") -> str:
    """Create a new Aseprite canvas with specified dimensions.

    Args:
        width: Width of the canvas in pixels
        height: Height of the canvas in pixels
        filename: Name of the output file (default: canvas.aseprite)
    """
    script = f"""
    local spr = Sprite({width}, {height})
    spr:saveAs("{filename}")
    return "Canvas created successfully: {filename}"
    """
    
    success, output = AsepriteCommand.execute_lua_script(script)
    
    if success:
        return f"Canvas created successfully: {filename}"
    else:
        return f"Failed to create canvas: {output}"

@mcp.tool()
async def add_layer(filename: str, layer_name: str) -> str:
    """Add a new layer to the Aseprite file.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Name of the new layer
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    
    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end
    
    app.transaction(function()
        spr:newLayer()
        app.activeLayer.name = "{layer_name}"
    end)
    
    spr:saveAs(spr.filename)
    return "Layer added successfully"
    """
    
    success, output = AsepriteCommand.execute_lua_script(script, filename)
    
    if success:
        return f"Layer '{layer_name}' added successfully to {filename}"
    else:
        return f"Failed to add layer: {output}"

@mcp.tool()
async def add_frame(filename: str) -> str:
    """Add a new frame to the Aseprite file.

    Args:
        filename: Name of the Aseprite file to modify
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    
    script = """
    local spr = app.activeSprite
    if not spr then return "No active sprite" end
    
    app.transaction(function()
        spr:newFrame()
    end)
    
    spr:saveAs(spr.filename)
    return "Frame added successfully"
    """
    
    success, output = AsepriteCommand.execute_lua_script(script, filename)
    
    if success:
        return f"New frame added successfully to {filename}"
    else:
        return f"Failed to add frame: {output}"

@mcp.tool()
async def set_frame(filename: str, frame_index: int) -> str:
    """Set the active frame by index (1-based).

    Args:
        filename: Name of the Aseprite file to modify
        frame_index: Frame index starting at 1
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then
        return "Frame index out of range"
    end

    app.transaction(function()
        app.activeFrame = spr.frames[idx]
    end)

    spr:saveAs(spr.filename)
    return "Active frame set"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)

    if success:
        return f"Active frame set to {frame_index} in {filename}"
    else:
        return f"Failed to set frame: {output}"

@mcp.tool()
async def set_frame_duration(filename: str, frame_index: int, duration_ms: int) -> str:
    """Set the duration of a frame in milliseconds.

    Args:
        filename: Name of the Aseprite file to modify
        frame_index: Frame index starting at 1
        duration_ms: Duration in milliseconds
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then
        return "Frame index out of range"
    end

    app.transaction(function()
        spr.frames[idx].duration = {duration_ms} / 1000.0
    end)

    spr:saveAs(spr.filename)
    return "Frame duration set"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)

    if success:
        return f"Frame {frame_index} duration set to {duration_ms}ms in {filename}"
    else:
        return f"Failed to set frame duration: {output}"

@mcp.tool()
async def set_layer(filename: str, layer_name: str, create_if_missing: bool = False) -> str:
    """Set the active layer by name.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to activate
        create_if_missing: Create layer if it does not exist
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    create_flag = "true" if create_if_missing else "false"

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

    app.transaction(function()
        if not target then
            if {create_flag} then
                target = spr:newLayer()
                target.name = "{layer_name}"
            else
                return
            end
        end
        app.activeLayer = target
    end)

    spr:saveAs(spr.filename)
    return "Active layer set"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)

    if success:
        return f"Active layer set to '{layer_name}' in {filename}"
    else:
        return f"Failed to set layer: {output}"
