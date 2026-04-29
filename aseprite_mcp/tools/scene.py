import os
from typing import List
from ..core.commands import AsepriteCommand, lua_escape, reject_traversal
from .. import mcp

@mcp.tool()
async def copy_layers_between_sprites(
    source_filename: str,
    target_filename: str,
    layer_names: List[str],
    replace: bool = True,
    create_missing_frames: bool = True
) -> str:
    """Copy layers by name from a source sprite to a target sprite.

    Args:
        source_filename: Source .aseprite file
        target_filename: Target .aseprite file
        layer_names: List of layer names to copy
        replace: Overwrite existing cels in target layers
        create_missing_frames: Add frames to target if needed
    """
    if not os.path.exists(source_filename):
        return f"File {source_filename} not found"
    if not os.path.exists(target_filename):
        return f"File {target_filename} not found"
    if not layer_names:
        return "Layer names list cannot be empty"
    err = reject_traversal(source_filename) or reject_traversal(target_filename)
    if err:
        return err

    src_path = lua_escape(source_filename.replace("\\", "/"))
    dst_path = lua_escape(target_filename.replace("\\", "/"))
    replace_flag = "true" if replace else "false"
    create_frames_flag = "true" if create_missing_frames else "false"
    layers_lua = "{" + ",".join([f"\"{lua_escape(name)}\"" for name in layer_names]) + "}"

    script = f"""
    local src = app.open("{src_path}")
    if not src then return "Source sprite not opened" end
    local dst = app.open("{dst_path}")
    if not dst then return "Target sprite not opened" end

    local function find_layer(spr, name)
        for _, layer in ipairs(spr.layers) do
            if layer.name == name then return layer end
        end
        return nil
    end

    local names = {layers_lua}
    local missing = {{}}

    app.transaction(function()
        if {create_frames_flag} then
            while #dst.frames < #src.frames do
                dst:newFrame()
            end
        end

        for _, name in ipairs(names) do
            local src_layer = find_layer(src, name)
            if not src_layer then
                table.insert(missing, name)
            else
                local dst_layer = find_layer(dst, name)
                if not dst_layer then
                    dst_layer = dst:newLayer()
                    dst_layer.name = name
                end
                if {replace_flag} then
                    for i = 1, #dst.frames do
                        local cel = dst_layer:cel(dst.frames[i])
                        if cel then dst:deleteCel(cel) end
                    end
                end
                for i = 1, #src.frames do
                    if i <= #dst.frames then
                        local src_cel = src_layer:cel(src.frames[i])
                        if src_cel then
                            local dst_cel = dst_layer:cel(dst.frames[i])
                            if dst_cel and {replace_flag} then
                                dst:deleteCel(dst_cel)
                                dst_cel = nil
                            end
                            if not dst_cel then
                                local img = src_cel.image:clone()
                                dst:newCel(dst_layer, dst.frames[i], img, src_cel.position)
                            end
                        end
                    end
                end
            end
        end
    end)

    dst:saveAs(dst.filename)
    if #missing > 0 then
        return "Copied layers with missing: " .. table.concat(missing, ", ")
    end
    return "Layers copied"
    """

    success, output = AsepriteCommand.execute_lua_script(script)
    if success:
        return f"Layers copied from {source_filename} to {target_filename}"
    return f"Failed to copy layers: {output}"
