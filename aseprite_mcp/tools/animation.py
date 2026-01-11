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

@mcp.tool()
async def duplicate_frame_range(filename: str, start_frame: int, end_frame: int, times: int = 1) -> str:
    """Duplicate a frame range and append copies to the end.

    Args:
        filename: Name of the Aseprite file to modify
        start_frame: Starting frame index (1-based)
        end_frame: Ending frame index (1-based, inclusive)
        times: Number of times to append the range (default: 1)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if times < 1:
        return "Times must be >= 1"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local start_idx = {start_frame}
    local end_idx = {end_frame}
    local times = {times}
    if start_idx < 1 or end_idx > #spr.frames or start_idx > end_idx then
        return "Frame range out of bounds"
    end
    if times < 1 then return "Times must be >= 1" end

    app.transaction(function()
        for t = 1, times do
            for fi = start_idx, end_idx do
                app.activeFrame = spr.frames[#spr.frames]
                local new_frame = spr:newFrame()
                for _, layer in ipairs(spr.layers) do
                    if not layer.isGroup then
                        local cel = layer:cel(spr.frames[fi])
                        if cel then
                            local img = cel.image:clone()
                            spr:newCel(layer, new_frame, img, cel.position)
                        end
                    end
                end
            end
        end
    end)

    spr:saveAs(spr.filename)
    return "Frame range duplicated"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Duplicated frames {start_frame}-{end_frame} (x{times}) in {filename}"
    return f"Failed to duplicate frame range: {output}"

@mcp.tool()
async def set_cel_position(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int,
    y: int,
    create_if_missing: bool = False,
    source_frame_index: int | None = None
) -> str:
    """Set a cel's position in a specific layer and frame.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        frame_index: Frame index starting at 1
        x: X position in pixels
        y: Y position in pixels
        create_if_missing: Create the cel if it does not exist
        source_frame_index: Optional frame to copy the cel image from
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    source_idx = "nil" if source_frame_index is None else str(source_frame_index)
    create_flag = "true" if create_if_missing else "false"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local target_layer = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{layer_name}" then
            target_layer = layer
            break
        end
    end
    if not target_layer then return "Layer not found" end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then
        return "Frame index out of range"
    end

    app.transaction(function()
        local frame = spr.frames[idx]
        local cel = target_layer:cel(frame)
        if not cel and {create_flag} then
            local source_frame = {source_idx}
            if source_frame == nil then
                source_frame = idx
            end
            if source_frame < 1 or source_frame > #spr.frames then
                return
            end
            local source_cel = target_layer:cel(spr.frames[source_frame])
            if source_cel then
                local img = source_cel.image:clone()
                cel = spr:newCel(target_layer, frame, img, source_cel.position)
            else
                local img = Image(spr.width, spr.height, spr.colorMode)
                cel = spr:newCel(target_layer, frame, img, Point(0, 0))
            end
        end
        if not cel then return end
        cel.position = Point({x}, {y})
    end)

    spr:saveAs(spr.filename)
    return "Cel position set"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Cel position set to ({x}, {y}) on '{layer_name}' frame {frame_index} in {filename}"
    return f"Failed to set cel position: {output}"

@mcp.tool()
async def tween_cel_positions(
    filename: str,
    layer_name: str,
    start_frame: int,
    end_frame: int,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    create_missing_cels: bool = False,
    source_frame_index: int | None = None
) -> str:
    """Tween cel positions linearly across a frame range.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        start_frame: Starting frame index (1-based)
        end_frame: Ending frame index (1-based, inclusive)
        start_x: Starting X position in pixels
        start_y: Starting Y position in pixels
        end_x: Ending X position in pixels
        end_y: Ending Y position in pixels
        create_missing_cels: Create missing cels during tween
        source_frame_index: Optional frame to copy the cel image from
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    create_flag = "true" if create_missing_cels else "false"
    source_idx = "nil" if source_frame_index is None else str(source_frame_index)

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local target_layer = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{layer_name}" then
            target_layer = layer
            break
        end
    end
    if not target_layer then return "Layer not found" end

    local start_idx = {start_frame}
    local end_idx = {end_frame}
    if start_idx < 1 or end_idx > #spr.frames or start_idx > end_idx then
        return "Frame range out of bounds"
    end

    local span = end_idx - start_idx
    app.transaction(function()
        for fi = start_idx, end_idx do
            local t = 0
            if span > 0 then
                t = (fi - start_idx) / span
            end
            local x = math.floor({start_x} + ({end_x} - {start_x}) * t + 0.5)
            local y = math.floor({start_y} + ({end_y} - {start_y}) * t + 0.5)
            local frame = spr.frames[fi]
            local cel = target_layer:cel(frame)
            if not cel and {create_flag} then
                local source_frame = {source_idx}
                if source_frame == nil then
                    source_frame = start_idx
                end
                local source_cel = target_layer:cel(spr.frames[source_frame])
                if source_cel then
                    local img = source_cel.image:clone()
                    cel = spr:newCel(target_layer, frame, img, source_cel.position)
                else
                    local img = Image(spr.width, spr.height, spr.colorMode)
                    cel = spr:newCel(target_layer, frame, img, Point(0, 0))
                end
            end
            if cel then
                cel.position = Point(x, y)
            end
        end
    end)

    spr:saveAs(spr.filename)
    return "Cel positions tweened"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Tweened cel positions on '{layer_name}' frames {start_frame}-{end_frame} in {filename}"
    return f"Failed to tween cel positions: {output}"

@mcp.tool()
async def offset_cel_positions(
    filename: str,
    layer_name: str,
    start_frame: int,
    end_frame: int,
    dx: int,
    dy: int
) -> str:
    """Offset cel positions by a delta across a frame range.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        start_frame: Starting frame index (1-based)
        end_frame: Ending frame index (1-based, inclusive)
        dx: X delta in pixels
        dy: Y delta in pixels
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local target_layer = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{layer_name}" then
            target_layer = layer
            break
        end
    end
    if not target_layer then return "Layer not found" end

    local start_idx = {start_frame}
    local end_idx = {end_frame}
    if start_idx < 1 or end_idx > #spr.frames or start_idx > end_idx then
        return "Frame range out of bounds"
    end

    app.transaction(function()
        for fi = start_idx, end_idx do
            local frame = spr.frames[fi]
            local cel = target_layer:cel(frame)
            if cel then
                local pos = cel.position
                cel.position = Point(pos.x + {dx}, pos.y + {dy})
            end
        end
    end)

    spr:saveAs(spr.filename)
    return "Cel positions offset"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Offset cel positions by ({dx}, {dy}) on '{layer_name}' frames {start_frame}-{end_frame} in {filename}"
    return f"Failed to offset cel positions: {output}"

@mcp.tool()
async def create_cel(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int = 0,
    y: int = 0
) -> str:
    """Create an empty cel on a layer/frame.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        frame_index: Frame index starting at 1
        x: X position in pixels
        y: Y position in pixels
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then return "Frame index out of range" end

    local target = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{layer_name}" then target = layer break end
    end
    if not target then return "Layer not found" end

    app.transaction(function()
        local frame = spr.frames[idx]
        local cel = target:cel(frame)
        if cel then return end
        local img = Image(spr.width, spr.height, spr.colorMode)
        spr:newCel(target, frame, img, Point({x}, {y}))
    end)

    spr:saveAs(spr.filename)
    return "Cel created"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Cel created on '{layer_name}' frame {frame_index} in {filename}"
    return f"Failed to create cel: {output}"

@mcp.tool()
async def clear_cel(filename: str, layer_name: str, frame_index: int) -> str:
    """Delete a cel on a layer/frame."""
    if not os.path.exists(filename):
        return f"File {filename} not found"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then return "Frame index out of range" end

    local target = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{layer_name}" then target = layer break end
    end
    if not target then return "Layer not found" end

    app.transaction(function()
        local frame = spr.frames[idx]
        local cel = target:cel(frame)
        if cel then
            spr:deleteCel(cel)
        end
    end)

    spr:saveAs(spr.filename)
    return "Cel cleared"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Cel cleared on '{layer_name}' frame {frame_index} in {filename}"
    return f"Failed to clear cel: {output}"

@mcp.tool()
async def copy_cel(
    filename: str,
    layer_name: str,
    source_frame: int,
    target_frame: int,
    replace: bool = True
) -> str:
    """Copy a cel from one frame to another."""
    if not os.path.exists(filename):
        return f"File {filename} not found"

    replace_flag = "true" if replace else "false"
    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local src_idx = {source_frame}
    local dst_idx = {target_frame}
    if src_idx < 1 or src_idx > #spr.frames then return "Source frame out of range" end
    if dst_idx < 1 or dst_idx > #spr.frames then return "Target frame out of range" end

    local target = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{layer_name}" then target = layer break end
    end
    if not target then return "Layer not found" end

    app.transaction(function()
        local src = target:cel(spr.frames[src_idx])
        if not src then return end
        local dst = target:cel(spr.frames[dst_idx])
        if dst and {replace_flag} then
            spr:deleteCel(dst)
        end
        if not dst then
            local img = src.image:clone()
            spr:newCel(target, spr.frames[dst_idx], img, src.position)
        end
    end)

    spr:saveAs(spr.filename)
    return "Cel copied"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Cel copied on '{layer_name}' from frame {source_frame} to {target_frame} in {filename}"
    return f"Failed to copy cel: {output}"

@mcp.tool()
async def copy_frame(
    filename: str,
    source_frame: int,
    target_frame: int | None = None,
    overwrite: bool = True
) -> str:
    """Copy all cels from a source frame to a target frame (or append)."""
    if not os.path.exists(filename):
        return f"File {filename} not found"

    overwrite_flag = "true" if overwrite else "false"
    target_idx = "nil" if target_frame is None else str(target_frame)

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local src_idx = {source_frame}
    if src_idx < 1 or src_idx > #spr.frames then return "Source frame out of range" end

    local dst_idx = {target_idx}
    app.transaction(function()
        local dst_frame = nil
        if dst_idx == nil then
            dst_frame = spr:newFrame()
        else
            if dst_idx < 1 or dst_idx > #spr.frames then return end
            dst_frame = spr.frames[dst_idx]
            if {overwrite_flag} then
                for _, layer in ipairs(spr.layers) do
                    if not layer.isGroup then
                        local cel = layer:cel(dst_frame)
                        if cel then spr:deleteCel(cel) end
                    end
                end
            end
        end

        for _, layer in ipairs(spr.layers) do
            if not layer.isGroup then
                local cel = layer:cel(spr.frames[src_idx])
                if cel then
                    local img = cel.image:clone()
                    spr:newCel(layer, dst_frame, img, cel.position)
                end
            end
        end
    end)

    spr:saveAs(spr.filename)
    return "Frame copied"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        if target_frame is None:
            return f"Frame {source_frame} copied to new frame in {filename}"
        return f"Frame {source_frame} copied to frame {target_frame} in {filename}"
    return f"Failed to copy frame: {output}"

@mcp.tool()
async def set_tag(
    filename: str,
    name: str,
    from_frame: int,
    to_frame: int,
    direction: str = "forward"
) -> str:
    """Create or update an animation tag on the sprite."""
    if not os.path.exists(filename):
        return f"File {filename} not found"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local start_idx = {from_frame}
    local end_idx = {to_frame}
    if start_idx < 1 or end_idx > #spr.frames or start_idx > end_idx then
        return "Frame range out of bounds"
    end

    local tag = nil
    for _, t in ipairs(spr.tags) do
        if t.name == "{name}" then tag = t break end
    end
    if not tag then
        tag = spr:newTag(start_idx, end_idx)
    else
        tag.fromFrame = spr.frames[start_idx]
        tag.toFrame = spr.frames[end_idx]
    end
    tag.name = "{name}"

    spr:saveAs(spr.filename)
    return "Tag set"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        if direction != "forward":
            return f"Tag '{name}' set to frames {from_frame}-{to_frame} in {filename} (direction ignored)"
        return f"Tag '{name}' set to frames {from_frame}-{to_frame} in {filename}"
    return f"Failed to set tag: {output}"

@mcp.tool()
async def set_onion_skin(
    filename: str,
    enabled: bool = True,
    before: int = 2,
    after: int = 2,
    opacity: int = 128
) -> str:
    """Configure onion skin settings for Aseprite."""
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if before < 0 or after < 0:
        return "Before/after must be >= 0"
    if opacity < 0 or opacity > 255:
        return "Opacity must be between 0 and 255"

    return (
        "Onion skin settings are UI-only in batch mode; no changes applied "
        f"(enabled={enabled}, before={before}, after={after}, opacity={opacity})"
    )

@mcp.tool()
async def propagate_cels(
    filename: str,
    layer_names: list[str],
    source_frame: int,
    start_frame: int,
    end_frame: int,
    replace: bool = True
) -> str:
    """Copy cels from a source frame to a range of frames for specific layers.

    Args:
        filename: Name of the Aseprite file to modify
        layer_names: List of layer names to copy
        source_frame: Frame index to copy from (1-based)
        start_frame: Start frame index (1-based)
        end_frame: End frame index (1-based, inclusive)
        replace: Whether to overwrite existing cels (default: True)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if not layer_names:
        return "Layer names list cannot be empty"

    replace_flag = "true" if replace else "false"
    layers_lua = "{" + ",".join([f"\"{name}\"" for name in layer_names]) + "}"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local src_idx = {source_frame}
    local start_idx = {start_frame}
    local end_idx = {end_frame}
    if src_idx < 1 or src_idx > #spr.frames then return "Source frame out of range" end
    if start_idx < 1 or end_idx > #spr.frames or start_idx > end_idx then
        return "Frame range out of bounds"
    end

    local name_list = {layers_lua}
    local targets = {{}}
    for _, name in ipairs(name_list) do
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
            if fi ~= src_idx then
                local dst_frame = spr.frames[fi]
                for _, layer in ipairs(targets) do
                    local src_cel = layer:cel(spr.frames[src_idx])
                    if src_cel then
                        local dst_cel = layer:cel(dst_frame)
                        if dst_cel and {replace_flag} then
                            spr:deleteCel(dst_cel)
                            dst_cel = nil
                        end
                        if not dst_cel then
                            local img = src_cel.image:clone()
                            spr:newCel(layer, dst_frame, img, src_cel.position)
                        end
                    end
                end
            end
        end
    end)

    spr:saveAs(spr.filename)
    return "Cels propagated"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return (
            f"Propagated cels from frame {source_frame} to frames {start_frame}-{end_frame} "
            f"for layers {', '.join(layer_names)} in {filename}"
        )
    return f"Failed to propagate cels: {output}"

@mcp.tool()
async def tween_cel_positions_eased(
    filename: str,
    layer_name: str,
    start_frame: int,
    end_frame: int,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    easing: str = "smoothstep",
    create_missing_cels: bool = False,
    source_frame_index: int | None = None
) -> str:
    """Tween cel positions with easing across a frame range."""
    if not os.path.exists(filename):
        return f"File {filename} not found"

    easing = (easing or "smoothstep").lower().strip()
    if easing not in {"linear", "ease_in", "ease_out", "ease_in_out", "smoothstep"}:
        return "Unsupported easing (linear, ease_in, ease_out, ease_in_out, smoothstep)"

    create_flag = "true" if create_missing_cels else "false"
    source_idx = "nil" if source_frame_index is None else str(source_frame_index)

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local target_layer = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{layer_name}" then
            target_layer = layer
            break
        end
    end
    if not target_layer then return "Layer not found" end

    local start_idx = {start_frame}
    local end_idx = {end_frame}
    if start_idx < 1 or end_idx > #spr.frames or start_idx > end_idx then
        return "Frame range out of bounds"
    end

    local function ease(t)
        local mode = "{easing}"
        if mode == "linear" then return t end
        if mode == "ease_in" then return t * t end
        if mode == "ease_out" then return 1 - (1 - t) * (1 - t) end
        if mode == "ease_in_out" then
            if t < 0.5 then return 2 * t * t end
            local u = -2 * t + 2
            return 1 - (u * u) / 2
        end
        return t * t * (3 - 2 * t)
    end

    local span = end_idx - start_idx
    app.transaction(function()
        for fi = start_idx, end_idx do
            local t = 0
            if span > 0 then
                t = (fi - start_idx) / span
            end
            local e = ease(t)
            local x = math.floor({start_x} + ({end_x} - {start_x}) * e + 0.5)
            local y = math.floor({start_y} + ({end_y} - {start_y}) * e + 0.5)
            local frame = spr.frames[fi]
            local cel = target_layer:cel(frame)
            if not cel and {create_flag} then
                local source_frame = {source_idx}
                if source_frame == nil then
                    source_frame = start_idx
                end
                local source_cel = target_layer:cel(spr.frames[source_frame])
                if source_cel then
                    local img = source_cel.image:clone()
                    cel = spr:newCel(target_layer, frame, img, source_cel.position)
                else
                    local img = Image(spr.width, spr.height, spr.colorMode)
                    cel = spr:newCel(target_layer, frame, img, Point(0, 0))
                end
            end
            if cel then
                cel.position = Point(x, y)
            end
        end
    end)

    spr:saveAs(spr.filename)
    return "Cel positions tweened with easing"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return (
            f"Tweened cel positions ({easing}) on '{layer_name}' frames {start_frame}-{end_frame} "
            f"in {filename}"
        )
    return f"Failed to tween cel positions with easing: {output}"

@mcp.tool()
async def tween_cel_opacity_eased(
    filename: str,
    layer_name: str,
    start_frame: int,
    end_frame: int,
    start_opacity: int,
    end_opacity: int,
    easing: str = "smoothstep",
    create_missing_cels: bool = False,
    source_frame_index: int | None = None
) -> str:
    """Tween cel opacity with easing across a frame range."""
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if start_opacity < 0 or start_opacity > 255 or end_opacity < 0 or end_opacity > 255:
        return "Opacity must be between 0 and 255"

    easing = (easing or "smoothstep").lower().strip()
    if easing not in {"linear", "ease_in", "ease_out", "ease_in_out", "smoothstep"}:
        return "Unsupported easing (linear, ease_in, ease_out, ease_in_out, smoothstep)"

    create_flag = "true" if create_missing_cels else "false"
    source_idx = "nil" if source_frame_index is None else str(source_frame_index)

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local target_layer = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{layer_name}" then
            target_layer = layer
            break
        end
    end
    if not target_layer then return "Layer not found" end

    local start_idx = {start_frame}
    local end_idx = {end_frame}
    if start_idx < 1 or end_idx > #spr.frames or start_idx > end_idx then
        return "Frame range out of bounds"
    end

    local function ease(t)
        local mode = "{easing}"
        if mode == "linear" then return t end
        if mode == "ease_in" then return t * t end
        if mode == "ease_out" then return 1 - (1 - t) * (1 - t) end
        if mode == "ease_in_out" then
            if t < 0.5 then return 2 * t * t end
            local u = -2 * t + 2
            return 1 - (u * u) / 2
        end
        return t * t * (3 - 2 * t)
    end

    local span = end_idx - start_idx
    app.transaction(function()
        for fi = start_idx, end_idx do
            local t = 0
            if span > 0 then
                t = (fi - start_idx) / span
            end
            local e = ease(t)
            local op = math.floor({start_opacity} + ({end_opacity} - {start_opacity}) * e + 0.5)
            if op < 0 then op = 0 end
            if op > 255 then op = 255 end
            local frame = spr.frames[fi]
            local cel = target_layer:cel(frame)
            if not cel and {create_flag} then
                local source_frame = {source_idx}
                if source_frame == nil then
                    source_frame = start_idx
                end
                local source_cel = target_layer:cel(spr.frames[source_frame])
                if source_cel then
                    local img = source_cel.image:clone()
                    cel = spr:newCel(target_layer, frame, img, source_cel.position)
                else
                    local img = Image(spr.width, spr.height, spr.colorMode)
                    cel = spr:newCel(target_layer, frame, img, Point(0, 0))
                end
            end
            if cel then
                cel.opacity = op
            end
        end
    end)

    spr:saveAs(spr.filename)
    return "Cel opacity tweened with easing"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return (
            f"Tweened cel opacity ({easing}) on '{layer_name}' frames {start_frame}-{end_frame} "
            f"in {filename}"
        )
    return f"Failed to tween cel opacity with easing: {output}"

@mcp.tool()
async def tween_cel_scale_eased(
    filename: str,
    layer_name: str,
    start_frame: int,
    end_frame: int,
    start_scale: float,
    end_scale: float,
    easing: str = "smoothstep",
    anchor: str = "center",
    replace: bool = True,
    create_missing_cels: bool = True,
    source_frame_index: int | None = None
) -> str:
    """Tween cel scale with easing across a frame range."""
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if start_scale <= 0 or end_scale <= 0:
        return "Scale must be > 0"

    easing = (easing or "smoothstep").lower().strip()
    if easing not in {"linear", "ease_in", "ease_out", "ease_in_out", "smoothstep"}:
        return "Unsupported easing (linear, ease_in, ease_out, ease_in_out, smoothstep)"

    anchor = (anchor or "center").lower().strip()
    if anchor not in {"center", "topleft"}:
        return "Unsupported anchor (center, topleft)"

    create_flag = "true" if create_missing_cels else "false"
    replace_flag = "true" if replace else "false"
    source_idx = "nil" if source_frame_index is None else str(source_frame_index)

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local target_layer = nil
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{layer_name}" then
            target_layer = layer
            break
        end
    end
    if not target_layer then return "Layer not found" end

    local start_idx = {start_frame}
    local end_idx = {end_frame}
    if start_idx < 1 or end_idx > #spr.frames or start_idx > end_idx then
        return "Frame range out of bounds"
    end

    local source_frame = {source_idx}
    if source_frame == nil then
        source_frame = start_idx
    end
    if source_frame < 1 or source_frame > #spr.frames then
        return "Source frame out of range"
    end

    local source_cel = target_layer:cel(spr.frames[source_frame])
    if not source_cel then
        return "Source cel not found"
    end

    local base_img = source_cel.image:clone()
    local base_w = base_img.width
    local base_h = base_img.height
    local base_pos = source_cel.position

    local function ease(t)
        local mode = "{easing}"
        if mode == "linear" then return t end
        if mode == "ease_in" then return t * t end
        if mode == "ease_out" then return 1 - (1 - t) * (1 - t) end
        if mode == "ease_in_out" then
            if t < 0.5 then return 2 * t * t end
            local u = -2 * t + 2
            return 1 - (u * u) / 2
        end
        return t * t * (3 - 2 * t)
    end

    local span = end_idx - start_idx
    app.transaction(function()
        for fi = start_idx, end_idx do
            local t = 0
            if span > 0 then
                t = (fi - start_idx) / span
            end
            local e = ease(t)
            local scale = {start_scale} + ({end_scale} - {start_scale}) * e
            local new_w = math.max(1, math.floor(base_w * scale + 0.5))
            local new_h = math.max(1, math.floor(base_h * scale + 0.5))

            local dst_frame = spr.frames[fi]
            local dst_cel = target_layer:cel(dst_frame)
            if dst_cel and {replace_flag} then
                spr:deleteCel(dst_cel)
                dst_cel = nil
            end
            if not dst_cel and {create_flag} then
                local img = base_img:clone()
                img:resize(new_w, new_h)
                local pos_x = base_pos.x
                local pos_y = base_pos.y
                if "{anchor}" == "center" then
                    local cx = base_pos.x + base_w / 2
                    local cy = base_pos.y + base_h / 2
                    pos_x = math.floor(cx - new_w / 2 + 0.5)
                    pos_y = math.floor(cy - new_h / 2 + 0.5)
                end
                dst_cel = spr:newCel(target_layer, dst_frame, img, Point(pos_x, pos_y))
            end
        end
    end)

    spr:saveAs(spr.filename)
    return "Cel scale tweened with easing"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return (
            f"Tweened cel scale ({easing}) on '{layer_name}' frames {start_frame}-{end_frame} "
            f"in {filename}"
        )
    return f"Failed to tween cel scale with easing: {output}"
