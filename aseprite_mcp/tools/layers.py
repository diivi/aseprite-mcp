import os
from ..core.commands import AsepriteCommand, lua_escape
from ..core.lua import FIND_LAYER
from .. import mcp

_BLEND_MODES = {
    "normal": "BlendMode.NORMAL",
    "darken": "BlendMode.DARKEN",
    "multiply": "BlendMode.MULTIPLY",
    "color_burn": "BlendMode.COLOR_BURN",
    "lighten": "BlendMode.LIGHTEN",
    "screen": "BlendMode.SCREEN",
    "color_dodge": "BlendMode.COLOR_DODGE",
    "addition": "BlendMode.ADDITION",
    "overlay": "BlendMode.OVERLAY",
    "soft_light": "BlendMode.SOFT_LIGHT",
    "hard_light": "BlendMode.HARD_LIGHT",
    "difference": "BlendMode.DIFFERENCE",
    "exclusion": "BlendMode.EXCLUSION",
    "subtract": "BlendMode.SUBTRACT",
    "divide": "BlendMode.DIVIDE",
    "hue": "BlendMode.HSL_HUE",
    "saturation": "BlendMode.HSL_SATURATION",
    "color": "BlendMode.HSL_COLOR",
    "luminosity": "BlendMode.HSL_LUMINOSITY",
}


@mcp.tool()
async def delete_layer(filename: str, layer_name: str) -> str:
    """Delete a layer by name.

    Args:
        filename: Aseprite file to modify
        layer_name: Name of the layer to delete
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    safe_layer = lua_escape(layer_name)
    script = f"""
    {FIND_LAYER}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local target = find_layer(spr, "{safe_layer}")
    if not target then print("ERROR:Layer not found") return end
    if #spr.layers <= 1 then print("ERROR:Cannot delete the only layer") return end

    app.transaction(function()
        spr:deleteLayer(target)
    end)

    spr:saveAs(spr.filename)
    print("OK")
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return f"Layer '{layer_name}' deleted from {filename}"
    return f"Failed to delete layer: {output}"


@mcp.tool()
async def rename_layer(filename: str, layer_name: str, new_name: str) -> str:
    """Rename a layer.

    Args:
        filename: Aseprite file to modify
        layer_name: Current layer name
        new_name: New layer name
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if not new_name:
        return "New name cannot be empty"

    safe_layer = lua_escape(layer_name)
    safe_new = lua_escape(new_name)
    script = f"""
    {FIND_LAYER}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local target = find_layer(spr, "{safe_layer}")
    if not target then print("ERROR:Layer not found") return end

    app.transaction(function()
        target.name = "{safe_new}"
    end)

    spr:saveAs(spr.filename)
    print("OK")
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return f"Layer '{layer_name}' renamed to '{new_name}' in {filename}"
    return f"Failed to rename layer: {output}"


@mcp.tool()
async def duplicate_layer(
    filename: str, layer_name: str, new_name: str = "", group: str = ""
) -> str:
    """Duplicate a layer with all its cels across every frame.

    The copy inherits the source's opacity and blend mode. By default it is
    placed directly above the source layer; pass `group` to place it inside a
    group instead.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to duplicate, by name or "group/subgroup/layer" path
        new_name: Name for the copy (default: "<layer_name> copy")
        group: Optional group to place the copy inside, by name or
            "group/subgroup" path (default: directly above the source)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    final_name = new_name or f"{layer_name} copy"
    safe_layer = lua_escape(layer_name)
    safe_new = lua_escape(final_name)
    safe_group = lua_escape(group)
    script = f"""
    {FIND_LAYER}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local src = find_layer(spr, "{safe_layer}")
    if not src then print("ERROR:Layer not found") return end

    local parent = nil
    if "{safe_group}" ~= "" then
        parent = find_layer(spr, "{safe_group}")
        if not parent then print("ERROR:Group not found") return end
        if not parent.isGroup then print("ERROR:Target is not a group") return end
    end

    app.transaction(function()
        local copy = spr:newLayer()
        copy.name = "{safe_new}"
        copy.opacity = src.opacity
        copy.blendMode = src.blendMode
        if parent then
            copy.parent = parent
        else
            copy.stackIndex = src.stackIndex + 1
        end
        for _, frame in ipairs(spr.frames) do
            local cel = src:cel(frame)
            if cel then
                local c = spr:newCel(copy, frame, cel.image:clone(), cel.position)
                c.opacity = cel.opacity
            end
        end
    end)

    spr:saveAs(spr.filename)
    print("OK")
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        location = f" inside group '{group}'" if group else ""
        return f"Layer '{layer_name}' duplicated as '{final_name}'{location} in {filename}"
    return f"Failed to duplicate layer: {output}"


@mcp.tool()
async def reorder_layer(filename: str, layer_name: str, position: int) -> str:
    """Move a layer to a new position in the layer stack.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to move
        position: Target stack position, 1-based where 1 is the bottom layer
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if position < 1:
        return "Position must be >= 1"

    safe_layer = lua_escape(layer_name)
    script = f"""
    {FIND_LAYER}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local target = find_layer(spr, "{safe_layer}")
    if not target then print("ERROR:Layer not found") return end
    if {position} > #spr.layers then print("ERROR:Position out of range") return end

    app.transaction(function()
        target.stackIndex = {position}
    end)

    spr:saveAs(spr.filename)
    print("OK")
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return f"Layer '{layer_name}' moved to position {position} in {filename}"
    return f"Failed to reorder layer: {output}"


@mcp.tool()
async def set_layer_blend_mode(filename: str, layer_name: str, mode: str) -> str:
    """Set a layer's blend mode.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to modify
        mode: One of: normal, darken, multiply, color_burn, lighten, screen,
            color_dodge, addition, overlay, soft_light, hard_light,
            difference, exclusion, subtract, divide, hue, saturation,
            color, luminosity
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    blend = _BLEND_MODES.get(mode.lower())
    if blend is None:
        return f"Unknown blend mode '{mode}'. Valid modes: {', '.join(sorted(_BLEND_MODES))}"

    safe_layer = lua_escape(layer_name)
    script = f"""
    {FIND_LAYER}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local target = find_layer(spr, "{safe_layer}")
    if not target then print("ERROR:Layer not found") return end

    app.transaction(function()
        target.blendMode = {blend}
    end)

    spr:saveAs(spr.filename)
    print("OK")
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return f"Layer '{layer_name}' blend mode set to {mode} in {filename}"
    return f"Failed to set blend mode: {output}"


@mcp.tool()
async def merge_layer_down(filename: str, layer_name: str) -> str:
    """Merge a layer into the layer directly below it.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to merge down (must not be the bottom layer)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    safe_layer = lua_escape(layer_name)
    script = f"""
    {FIND_LAYER}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local target = find_layer(spr, "{safe_layer}")
    if not target then print("ERROR:Layer not found") return end
    if target.stackIndex <= 1 then print("ERROR:Layer is the bottom layer; nothing to merge into") return end

    app.activeLayer = target
    app.command.MergeDownLayer()

    spr:saveAs(spr.filename)
    print("OK")
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return f"Layer '{layer_name}' merged down in {filename}"
    return f"Failed to merge layer down: {output}"


@mcp.tool()
async def flatten_sprite(filename: str) -> str:
    """Flatten all layers into a single layer.

    Args:
        filename: Aseprite file to modify
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    script = """
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    app.transaction(function()
        spr:flatten()
    end)

    spr:saveAs(spr.filename)
    print("OK")
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return f"Sprite flattened in {filename}"
    return f"Failed to flatten sprite: {output}"
