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

@mcp.tool()
async def audit_animation(
    filename: str,
    start_frame: int = 1,
    end_frame: int | None = None,
    layer_names: List[str] | None = None,
    overlap_pairs: List[str] | None = None,
    layer_frame_ranges: List[str] | None = None,
    report_cels: bool = False,
    report_bounds: bool = False,
    max_overlaps: int = 200,
    max_out_of_range: int = 200
) -> str:
    """Audit animation frames for overlaps and out-of-range layer activity.

    overlap_pairs format: ["layerA,layerB", "layerC:layerD"]
    layer_frame_ranges format: ["layer:1-8,17-24", "clouds:1-12"]
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if start_frame < 1:
        return "Start frame must be >= 1"
    if max_overlaps < 0 or max_out_of_range < 0:
        return "Max limits must be >= 0"

    layers_lua = "nil"
    if layer_names:
        layers_lua = "{" + ",".join([f"\"{name}\"" for name in layer_names]) + "}"

    pairs = []
    if overlap_pairs:
        for entry in overlap_pairs:
            if not entry:
                continue
            if "," in entry:
                left, right = entry.split(",", 1)
            elif ":" in entry:
                left, right = entry.split(":", 1)
            else:
                continue
            left = left.strip()
            right = right.strip()
            if left and right:
                pairs.append((left, right))
    pairs_lua = "{" + ",".join([f"{{\"{a}\",\"{b}\"}}" for a, b in pairs]) + "}"

    ranges = {}
    if layer_frame_ranges:
        for entry in layer_frame_ranges:
            if not entry or ":" not in entry:
                continue
            layer, ranges_part = entry.split(":", 1)
            layer = layer.strip()
            if not layer:
                continue
            spans = []
            for span in ranges_part.split(","):
                span = span.strip()
                if "-" in span:
                    left, right = span.split("-", 1)
                    try:
                        start = int(left)
                        end = int(right)
                    except ValueError:
                        continue
                    if start > 0 and end >= start:
                        spans.append((start, end))
            if spans:
                ranges[layer] = spans
    ranges_lua = "{"
    for layer, spans in ranges.items():
        span_list = ",".join([f"{{{s},{e}}}" for s, e in spans])
        ranges_lua += f"[\"{layer}\"]={{{span_list}}},"
    ranges_lua += "}"

    end_frame_val = "nil" if end_frame is None else str(end_frame)
    report_cels_flag = "true" if report_cels else "false"
    report_bounds_flag = "true" if report_bounds else "false"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local start_idx = {start_frame}
    local end_idx = {end_frame_val}
    if end_idx == nil then end_idx = #spr.frames end
    if start_idx < 1 or end_idx > #spr.frames or start_idx > end_idx then
        return "Frame range out of bounds"
    end

    local target_names = {layers_lua}
    local target_layers = {{}}
    if target_names == nil then
        for _, layer in ipairs(spr.layers) do
            if not layer.isGroup then
                table.insert(target_layers, layer)
            end
        end
    else
        for _, name in ipairs(target_names) do
            for _, layer in ipairs(spr.layers) do
                if layer.name == name then
                    table.insert(target_layers, layer)
                    break
                end
            end
        end
    end

    local layer_map = {{}}
    for _, layer in ipairs(target_layers) do
        layer_map[layer.name] = layer
    end

    local pairs = {pairs_lua}
    local ranges_by_layer = {ranges_lua}

    local overlaps = {{}}
    local out_of_range = {{}}
    local cel_entries = {{}}
    local total_cels = 0

    local function esc(s)
        local v = s:gsub("\\\\", "\\\\\\\\")
        v = v:gsub('"', '\\"')
        return v
    end

    local function in_ranges(layer_name, frame_index)
        local ranges = ranges_by_layer[layer_name]
        if not ranges then return true end
        for _, range in ipairs(ranges) do
            if frame_index >= range[1] and frame_index <= range[2] then
                return true
            end
        end
        return false
    end

    for fi = start_idx, end_idx do
        local frame = spr.frames[fi]
        local frame_cels = {{}}

        for _, layer in ipairs(target_layers) do
            local cel = layer:cel(frame)
            if cel then
                total_cels = total_cels + 1
                local img = cel.image
                local pos = cel.position
                if {report_cels_flag} then
                    if {report_bounds_flag} then
                        table.insert(frame_cels, {{
                            layer = layer.name,
                            x = pos.x,
                            y = pos.y,
                            w = img.width,
                            h = img.height
                        }})
                    else
                        table.insert(frame_cels, {{ layer = layer.name }})
                    end
                end

                if not in_ranges(layer.name, fi) then
                    if #out_of_range < {max_out_of_range} then
                        table.insert(out_of_range, {{ frame = fi, layer = layer.name }})
                    end
                end
            end
        end

        if {report_cels_flag} then
            table.insert(cel_entries, {{ frame = fi, cels = frame_cels }})
        end

        for _, pair in ipairs(pairs) do
            if #overlaps >= {max_overlaps} then break end
            local layer_a = layer_map[pair[1]]
            local layer_b = layer_map[pair[2]]
            if layer_a and layer_b then
                local cel_a = layer_a:cel(frame)
                local cel_b = layer_b:cel(frame)
                if cel_a and cel_b then
                    local a_pos = cel_a.position
                    local b_pos = cel_b.position
                    local a_w = cel_a.image.width
                    local a_h = cel_a.image.height
                    local b_w = cel_b.image.width
                    local b_h = cel_b.image.height
                    local overlap = a_pos.x < b_pos.x + b_w
                        and a_pos.x + a_w > b_pos.x
                        and a_pos.y < b_pos.y + b_h
                        and a_pos.y + a_h > b_pos.y
                    if overlap then
                        local entry = {{
                            frame = fi,
                            a = layer_a.name,
                            b = layer_b.name
                        }}
                        if {report_bounds_flag} then
                            entry.a_bounds = {{ a_pos.x, a_pos.y, a_w, a_h }}
                            entry.b_bounds = {{ b_pos.x, b_pos.y, b_w, b_h }}
                        end
                        table.insert(overlaps, entry)
                    end
                end
            end
        end
    end

    local parts = {{}}
    table.insert(parts, "{{")
    table.insert(parts, "\\"frames\\":{{\\"start\\":" .. start_idx .. ",\\"end\\":" .. end_idx .. "}},")
    table.insert(parts, "\\"summary\\":{{")
    table.insert(parts, "\\"total_layers\\":" .. #spr.layers .. ",")
    table.insert(parts, "\\"layers_checked\\":" .. #target_layers .. ",")
    table.insert(parts, "\\"total_cels\\":" .. total_cels .. ",")
    table.insert(parts, "\\"overlaps\\":" .. #overlaps .. ",")
    table.insert(parts, "\\"out_of_range\\":" .. #out_of_range)
    table.insert(parts, "}},")

    table.insert(parts, "\\"overlaps\\":[")
    for i, entry in ipairs(overlaps) do
        table.insert(parts, "{{\\"frame\\":" .. entry.frame .. ",\\"a\\":\\"" .. esc(entry.a) .. "\\",\\"b\\":\\"" .. esc(entry.b) .. "\\"")
        if entry.a_bounds then
            table.insert(parts, ",\\"a_bounds\\":[" .. entry.a_bounds[1] .. "," .. entry.a_bounds[2] .. "," .. entry.a_bounds[3] .. "," .. entry.a_bounds[4] .. "]")
            table.insert(parts, ",\\"b_bounds\\":[" .. entry.b_bounds[1] .. "," .. entry.b_bounds[2] .. "," .. entry.b_bounds[3] .. "," .. entry.b_bounds[4] .. "]")
        end
        table.insert(parts, "}}")
        if i < #overlaps then table.insert(parts, ",") end
    end
    table.insert(parts, "],")

    table.insert(parts, "\\"out_of_range\\":[")
    for i, entry in ipairs(out_of_range) do
        table.insert(parts, "{{\\"frame\\":" .. entry.frame .. ",\\"layer\\":\\"" .. esc(entry.layer) .. "\\"}}")
        if i < #out_of_range then table.insert(parts, ",") end
    end
    table.insert(parts, "]")

    if {report_cels_flag} then
        table.insert(parts, ",\\"cels\\":[")
        for i, entry in ipairs(cel_entries) do
            table.insert(parts, "{{\\"frame\\":" .. entry.frame .. ",\\"cels\\":[")
            for j, cel in ipairs(entry.cels) do
                if cel.w then
                    table.insert(parts, "{{\\"layer\\":\\"" .. esc(cel.layer) .. "\\",\\"x\\":" .. cel.x .. ",\\"y\\":" .. cel.y .. ",\\"w\\":" .. cel.w .. ",\\"h\\":" .. cel.h .. "}}")
                else
                    table.insert(parts, "{{\\"layer\\":\\"" .. esc(cel.layer) .. "\\"}}")
                end
                if j < #entry.cels then table.insert(parts, ",") end
            end
            table.insert(parts, "]}}")
            if i < #cel_entries then table.insert(parts, ",") end
        end
        table.insert(parts, "]")
    end

    table.insert(parts, "}}")
    return table.concat(parts)
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return output
    return f"Failed to audit animation: {output}"

@mcp.tool()
async def animation_sanitize(
    filename: str,
    start_frame: int = 1,
    end_frame: int | None = None,
    layer_names: List[str] | None = None,
    layer_order: List[str] | None = None,
    layer_frame_ranges: List[str] | None = None,
    ensure_layers: List[str] | None = None,
    overlap_pairs: List[str] | None = None,
    report_bounds: bool = False,
    max_overlaps: int = 200,
    out_of_range_action: str = "set_opacity_zero",
    out_of_range_opacity: int = 0,
    report_only: bool = False,
    include_stats: bool = True
) -> str:
    """Normalize animation consistency and optionally apply fixes.

    layer_frame_ranges format: ["layer:1-8,17-24", "clouds:1-12"]
    out_of_range_action: "set_opacity_zero", "delete_cels", "none"
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if start_frame < 1:
        return "Start frame must be >= 1"
    if max_overlaps < 0:
        return "max_overlaps must be >= 0"
    if out_of_range_action not in {"set_opacity_zero", "delete_cels", "none"}:
        return "Unsupported out_of_range_action"
    if out_of_range_opacity < 0 or out_of_range_opacity > 255:
        return "out_of_range_opacity must be 0-255"

    layers_lua = "nil"
    if layer_names:
        layers_lua = "{" + ",".join([f"\"{name}\"" for name in layer_names]) + "}"

    order_lua = "nil"
    if layer_order:
        order_lua = "{" + ",".join([f"\"{name}\"" for name in layer_order]) + "}"

    ensure_lua = "nil"
    if ensure_layers:
        ensure_lua = "{" + ",".join([f"\"{name}\"" for name in ensure_layers]) + "}"

    ranges = {}
    if layer_frame_ranges:
        for entry in layer_frame_ranges:
            if not entry or ":" not in entry:
                continue
            layer, ranges_part = entry.split(":", 1)
            layer = layer.strip()
            if not layer:
                continue
            spans = []
            for span in ranges_part.split(","):
                span = span.strip()
                if "-" in span:
                    left, right = span.split("-", 1)
                    try:
                        start = int(left)
                        end = int(right)
                    except ValueError:
                        continue
                    if start > 0 and end >= start:
                        spans.append((start, end))
            if spans:
                ranges[layer] = spans
    ranges_lua = "{"
    for layer, spans in ranges.items():
        span_list = ",".join([f"{{{s},{e}}}" for s, e in spans])
        ranges_lua += f"[\"{layer}\"]={{{span_list}}},"
    ranges_lua += "}"

    pairs = []
    if overlap_pairs:
        for entry in overlap_pairs:
            if not entry:
                continue
            if "," in entry:
                left, right = entry.split(",", 1)
            elif ":" in entry:
                left, right = entry.split(":", 1)
            else:
                continue
            left = left.strip()
            right = right.strip()
            if left and right:
                pairs.append((left, right))
    pairs_lua = "{" + ",".join([f"{{\"{a}\",\"{b}\"}}" for a, b in pairs]) + "}"

    end_frame_val = "nil" if end_frame is None else str(end_frame)
    report_only_flag = "true" if report_only else "false"
    report_bounds_flag = "true" if report_bounds else "false"
    include_stats_flag = "true" if include_stats else "false"

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local start_idx = {start_frame}
    local end_idx = {end_frame_val}
    if end_idx == nil then end_idx = #spr.frames end
    if start_idx < 1 or end_idx > #spr.frames or start_idx > end_idx then
        return "Frame range out of bounds"
    end

    local target_names = {layers_lua}
    local target_layers = {{}}
    if target_names == nil then
        for _, layer in ipairs(spr.layers) do
            if not layer.isGroup then
                table.insert(target_layers, layer)
            end
        end
    else
        for _, name in ipairs(target_names) do
            for _, layer in ipairs(spr.layers) do
                if layer.name == name then
                    table.insert(target_layers, layer)
                    break
                end
            end
        end
    end

    local ranges_by_layer = {ranges_lua}
    local order_names = {order_lua}
    local ensure_names = {ensure_lua}
    local pairs = {pairs_lua}

    local sanitized = {{
        reordered = false,
        ensured = 0,
        out_of_range = 0,
        opacity_set = 0,
        deleted = 0
    }}

    local analysis = {{
        total_layers = #spr.layers,
        layers_checked = #target_layers,
        total_cels = 0,
        empty_frames = 0,
        inactive_layers = {{}},
        overlaps = 0
    }}

    local layer_activity = {{}}
    local layer_stats = {{}}
    for _, layer in ipairs(target_layers) do
        layer_activity[layer.name] = 0
        layer_stats[layer.name] = {{
            frames_active = 0,
            cel_count = 0,
            full_canvas_cels = 0,
            min_x = nil,
            min_y = nil,
            max_x = nil,
            max_y = nil
        }}
    end

    local overlaps = {{}}
    local alerts = {{}}

    local function in_ranges(layer_name, frame_index)
        local ranges = ranges_by_layer[layer_name]
        if not ranges then return true end
        for _, range in ipairs(ranges) do
            if frame_index >= range[1] and frame_index <= range[2] then
                return true
            end
        end
        return false
    end

    app.transaction(function()
        if order_names ~= nil then
            local ordered = {{}}
            local seen = {{}}
            for _, name in ipairs(order_names) do
                for _, layer in ipairs(spr.layers) do
                    if layer.name == name and not layer.isGroup and not seen[layer] then
                        table.insert(ordered, layer)
                        seen[layer] = true
                        break
                    end
                end
            end
            for _, layer in ipairs(spr.layers) do
                if not layer.isGroup and not seen[layer] then
                    table.insert(ordered, layer)
                end
            end
            if not {report_only_flag} then
                for idx, layer in ipairs(ordered) do
                    layer.stackIndex = idx
                end
            end
            sanitized.reordered = true
        end

        if ensure_names ~= nil then
            for _, name in ipairs(ensure_names) do
                for _, layer in ipairs(spr.layers) do
                    if layer.name == name and not layer.isGroup then
                        for fi = start_idx, end_idx do
                            local frame = spr.frames[fi]
                            local cel = layer:cel(frame)
                            if not cel then
                                sanitized.ensured = sanitized.ensured + 1
                                if not {report_only_flag} then
                                    local img = Image(spr.width, spr.height, spr.colorMode)
                                    spr:newCel(layer, frame, img, Point(0, 0))
                                end
                            end
                        end
                        break
                    end
                end
            end
        end

        for fi = start_idx, end_idx do
            local has_cel = false
            local frame = spr.frames[fi]
            for _, layer in ipairs(target_layers) do
                local cel = layer:cel(frame)
                if cel then
                    has_cel = true
                    analysis.total_cels = analysis.total_cels + 1
                    layer_activity[layer.name] = (layer_activity[layer.name] or 0) + 1
                    local stats = layer_stats[layer.name]
                    if stats then
                        stats.cel_count = stats.cel_count + 1
                        stats.frames_active = stats.frames_active + 1
                        local img = cel.image
                        local pos = cel.position
                        local x1 = pos.x
                        local y1 = pos.y
                        local x2 = pos.x + img.width
                        local y2 = pos.y + img.height
                        if img.width == spr.width and img.height == spr.height then
                            stats.full_canvas_cels = stats.full_canvas_cels + 1
                        end
                        if stats.min_x == nil or x1 < stats.min_x then stats.min_x = x1 end
                        if stats.min_y == nil or y1 < stats.min_y then stats.min_y = y1 end
                        if stats.max_x == nil or x2 > stats.max_x then stats.max_x = x2 end
                        if stats.max_y == nil or y2 > stats.max_y then stats.max_y = y2 end
                    end
                    if not in_ranges(layer.name, fi) then
                        sanitized.out_of_range = sanitized.out_of_range + 1
                        if not {report_only_flag} then
                            if "{out_of_range_action}" == "delete_cels" then
                                spr:deleteCel(cel)
                                sanitized.deleted = sanitized.deleted + 1
                            elseif "{out_of_range_action}" == "set_opacity_zero" then
                                cel.opacity = {out_of_range_opacity}
                                sanitized.opacity_set = sanitized.opacity_set + 1
                            end
                        end
                    end
                end
            end
            if not has_cel then
                analysis.empty_frames = analysis.empty_frames + 1
            end

            if #pairs > 0 then
                for _, pair in ipairs(pairs) do
                    if #overlaps >= {max_overlaps} then break end
                    local layer_a = nil
                    local layer_b = nil
                    for _, layer in ipairs(target_layers) do
                        if layer.name == pair[1] then layer_a = layer end
                        if layer.name == pair[2] then layer_b = layer end
                    end
                    if layer_a and layer_b then
                        local cel_a = layer_a:cel(frame)
                        local cel_b = layer_b:cel(frame)
                        if cel_a and cel_b then
                            local a_pos = cel_a.position
                            local b_pos = cel_b.position
                            local a_w = cel_a.image.width
                            local a_h = cel_a.image.height
                            local b_w = cel_b.image.width
                            local b_h = cel_b.image.height
                            local overlap = a_pos.x < b_pos.x + b_w
                                and a_pos.x + a_w > b_pos.x
                                and a_pos.y < b_pos.y + b_h
                                and a_pos.y + a_h > b_pos.y
                            if overlap then
                                analysis.overlaps = analysis.overlaps + 1
                                local entry = {{
                                    frame = fi,
                                    a = layer_a.name,
                                    b = layer_b.name
                                }}
                                if {report_bounds_flag} then
                                    entry.a_bounds = {{ a_pos.x, a_pos.y, a_w, a_h }}
                                    entry.b_bounds = {{ b_pos.x, b_pos.y, b_w, b_h }}
                                end
                                table.insert(overlaps, entry)
                            end
                        end
                    end
                end
            end
        end
    end)

    for _, layer in ipairs(target_layers) do
        if layer_activity[layer.name] == 0 then
            table.insert(analysis.inactive_layers, layer.name)
        end
    end

    spr:saveAs(spr.filename)
    local parts = {{}}
    table.insert(parts, "{{")
    table.insert(parts, "\\"frames\\":{{\\"start\\":" .. start_idx .. ",\\"end\\":" .. end_idx .. "}},")
    table.insert(parts, "\\"reordered\\":" .. tostring(sanitized.reordered) .. ",")
    table.insert(parts, "\\"ensured\\":" .. sanitized.ensured .. ",")
    table.insert(parts, "\\"out_of_range\\":" .. sanitized.out_of_range .. ",")
    table.insert(parts, "\\"opacity_set\\":" .. sanitized.opacity_set .. ",")
    table.insert(parts, "\\"deleted\\":" .. sanitized.deleted .. ",")
    table.insert(parts, "\\"analysis\\":{{")
    table.insert(parts, "\\"total_layers\\":" .. analysis.total_layers .. ",")
    table.insert(parts, "\\"layers_checked\\":" .. analysis.layers_checked .. ",")
    table.insert(parts, "\\"total_cels\\":" .. analysis.total_cels .. ",")
    table.insert(parts, "\\"empty_frames\\":" .. analysis.empty_frames .. ",")
    table.insert(parts, "\\"overlaps\\":" .. analysis.overlaps .. ",")
    table.insert(parts, "\\"inactive_layers\\":[")
    for i, name in ipairs(analysis.inactive_layers) do
        table.insert(parts, '\\"' .. name .. '\\"')
        if i < #analysis.inactive_layers then table.insert(parts, ",") end
    end
    table.insert(parts, "]")
    table.insert(parts, "}}")

    if {include_stats_flag} then
        table.insert(parts, ",\\"layer_stats\\":{{")
        local count = 0
        for _, layer in ipairs(target_layers) do
            local stats = layer_stats[layer.name]
            if stats then
                count = count + 1
                table.insert(parts, '\\"' .. layer.name .. '\\":{{')
                table.insert(parts, '\\"frames_active\\":' .. stats.frames_active .. ",")
                table.insert(parts, '\\"cel_count\\":' .. stats.cel_count .. ",")
                table.insert(parts, '\\"full_canvas_cels\\":' .. stats.full_canvas_cels .. ",")
                if stats.min_x == nil then
                    table.insert(parts, '\\"bounds\\":null')
                else
                    table.insert(parts, '\\"bounds\\":[' .. stats.min_x .. "," .. stats.min_y .. "," .. stats.max_x .. "," .. stats.max_y .. "]")
                end
                table.insert(parts, "}}")
                if count < #target_layers then table.insert(parts, ",") end
            end
        end
        table.insert(parts, "}}")
    end

    if analysis.empty_frames > 0 then
        table.insert(alerts, "empty_frames_detected")
    end
    if sanitized.out_of_range > 0 then
        table.insert(alerts, "cels_out_of_range")
    end
    for _, layer in ipairs(target_layers) do
        local stats = layer_stats[layer.name]
        if stats and stats.full_canvas_cels > 0 then
            table.insert(alerts, "full_canvas_cels:" .. layer.name)
        end
    end
    if #alerts > 0 then
        table.insert(parts, ",\\"alerts\\":[")
        for i, msg in ipairs(alerts) do
            table.insert(parts, '\\"' .. msg .. '\\"')
            if i < #alerts then table.insert(parts, ",") end
        end
        table.insert(parts, "]")
    end

    if #overlaps > 0 then
        table.insert(parts, ",\\"overlap_samples\\":[")
        for i, entry in ipairs(overlaps) do
            table.insert(parts, "{{\\"frame\\":" .. entry.frame .. ",\\"a\\":\\"" .. entry.a .. "\\",\\"b\\":\\"" .. entry.b .. "\\"")
            if entry.a_bounds then
                table.insert(parts, ",\\"a_bounds\\":[" .. entry.a_bounds[1] .. "," .. entry.a_bounds[2] .. "," .. entry.a_bounds[3] .. "," .. entry.a_bounds[4] .. "]")
                table.insert(parts, ",\\"b_bounds\\":[" .. entry.b_bounds[1] .. "," .. entry.b_bounds[2] .. "," .. entry.b_bounds[3] .. "," .. entry.b_bounds[4] .. "]")
            end
            table.insert(parts, "}}")
            if i < #overlaps then table.insert(parts, ",") end
        end
        table.insert(parts, "]")
    end

    table.insert(parts, "}}")
    local output = table.concat(parts)
    print(output)
    return output
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return output
    return f"Failed to sanitize animation: {output}"
