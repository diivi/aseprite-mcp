import os
import json
from typing import List
from ..core.commands import AsepriteCommand
from .. import mcp

@mcp.tool()
async def ensure_layers_present(
    filename: str,
    layer_names: List[str],
    start_frame: int = 1,
    end_frame: int | None = None
) -> str:
    """Ensure cels exist for layers across a frame range."""
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if not layer_names:
        return "Layer names list cannot be empty"

    end_frame_val = "nil" if end_frame is None else str(end_frame)
    layers_lua = "{" + ",".join([f"\"{name}\"" for name in layer_names]) + "}"

    script = """
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local start_idx = __START__
    local end_idx = __END__
    if end_idx == nil then end_idx = #spr.frames end
    if start_idx < 1 or end_idx > #spr.frames or start_idx > end_idx then
        return "Frame range out of bounds"
    end

    local names = __LAYERS__
    local targets = {}
    for _, name in ipairs(names) do
        for _, layer in ipairs(spr.layers) do
            if layer.name == name then
                table.insert(targets, layer)
                break
            end
        end
    end
    if #targets == 0 then return "No layers found" end

    app.transaction(function()
        for fi = start_idx, end_idx do
            local frame = spr.frames[fi]
            for _, layer in ipairs(targets) do
                local cel = layer:cel(frame)
                if not cel then
                    local img = Image(spr.width, spr.height, spr.colorMode)
                    spr:newCel(layer, frame, img, Point(0, 0))
                end
            end
        end
    end)

    spr:saveAs(spr.filename)
    return "Cels ensured"
    """

    script = (
        script
        .replace("__START__", str(start_frame))
        .replace("__END__", end_frame_val)
        .replace("__LAYERS__", layers_lua)
    )

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return (
            f"Ensured cels for layers {', '.join(layer_names)} "
            f"on frames {start_frame}-{end_frame or 'end'} in {filename}"
        )
    return f"Failed to ensure cels: {output}"

@mcp.tool()
async def validate_scene(
    filename: str,
    required_layers: List[str],
    start_frame: int = 1,
    end_frame: int | None = None
) -> str:
    """Validate presence of layers and cels across a frame range.

    Returns JSON with missing layers and missing cels.
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if not required_layers:
        return "Required layers list cannot be empty"

    end_frame_val = "nil" if end_frame is None else str(end_frame)
    layers_lua = "{" + ",".join([f"\"{name}\"" for name in required_layers]) + "}"

    script = """
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local start_idx = __START__
    local end_idx = __END__
    if end_idx == nil then end_idx = #spr.frames end
    if start_idx < 1 or end_idx > #spr.frames or start_idx > end_idx then
        return "Frame range out of bounds"
    end

    local names = __LAYERS__
    local missing_layers = {}
    local missing_cels = {}

    local function find_layer(name)
        for _, layer in ipairs(spr.layers) do
            if layer.name == name then return layer end
        end
        return nil
    end

    for _, name in ipairs(names) do
        local layer = find_layer(name)
        if not layer then
            table.insert(missing_layers, name)
        else
            for fi = start_idx, end_idx do
                local frame = spr.frames[fi]
                if not layer:cel(frame) then
                    table.insert(missing_cels, {layer=name, frame=fi})
                end
            end
        end
    end

    local parts = {}
    table.insert(parts, "{")
    table.insert(parts, "\\"frames\\":" .. #spr.frames .. ",")
    table.insert(parts, "\\"range\\":{\\"start\\":" .. start_idx .. ",\\"end\\":" .. end_idx .. "},")
    table.insert(parts, "\\"missing_layers\\":[")
    for i, name in ipairs(missing_layers) do
        table.insert(parts, "\\""..name.."\\"")
        if i < #missing_layers then table.insert(parts, ",") end
    end
    table.insert(parts, "],")
    table.insert(parts, "\\"missing_cels\\":[")
    for i, entry in ipairs(missing_cels) do
        table.insert(parts, '{"layer":"' .. entry.layer .. '","frame":' .. entry.frame .. '}')
        if i < #missing_cels then table.insert(parts, ",") end
    end
    table.insert(parts, "]}")
    print(table.concat(parts))
    """

    script = (
        script
        .replace("__START__", str(start_frame))
        .replace("__END__", end_frame_val)
        .replace("__LAYERS__", layers_lua)
    )

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return output
    return f"Failed to validate scene: {output}"
