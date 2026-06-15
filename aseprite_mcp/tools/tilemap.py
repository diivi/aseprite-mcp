import json
import os
from typing import List, Dict, Any
from ..core.commands import AsepriteCommand, lua_escape
from ..core.lua import FIND_LAYER
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
async def create_tilemap_layer(
    filename: str,
    layer_name: str,
    tile_width: int,
    tile_height: int,
) -> str:
    """Create a tilemap layer with its own tileset.

    Sets the sprite grid to the tile size and adds a tilemap layer.
    Tile index 0 is always the empty tile; add real tiles with
    draw_on_tile (which creates tiles on demand).

    Args:
        filename: Aseprite file to modify
        layer_name: Name for the new tilemap layer
        tile_width: Tile width in pixels
        tile_height: Tile height in pixels
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if tile_width <= 0 or tile_height <= 0:
        return "Tile dimensions must be > 0"

    safe_layer = lua_escape(layer_name)
    script = f"""
    {FIND_LAYER}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    -- Duplicate-name guard is top-level only: the new layer is created at the
    -- root, and Aseprite permits the same name inside a different group, so a
    -- recursive find_layer would reject valid names.
    local name_taken = false
    for _, layer in ipairs(spr.layers) do
        if layer.name == "{safe_layer}" then name_taken = true break end
    end
    if name_taken then print("ERROR:Layer with that name already exists") return end

    app.transaction(function()
        spr.gridBounds = Rectangle(0, 0, {tile_width}, {tile_height})
        app.command.NewLayer {{ tilemap = true }}
        app.activeLayer.name = "{safe_layer}"
    end)

    spr:saveAs(spr.filename)
    print("OK")
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return (
            f"Tilemap layer '{layer_name}' created with {tile_width}x{tile_height} "
            f"tiles in {filename}"
        )
    return f"Failed to create tilemap layer: {output}"


@mcp.tool()
async def draw_on_tile(
    filename: str,
    layer_name: str,
    tile_index: int,
    pixels: List[Dict[str, Any]],
) -> str:
    """Draw pixels onto a tile in a tilemap layer's tileset.

    Coordinates are tile-local (0,0 = tile top-left). When tile_index
    equals the current tile count, a new tile is appended automatically.

    Args:
        filename: Aseprite file to modify
        layer_name: Tilemap layer whose tileset to edit
        tile_index: Tile to draw on (1 = first real tile; 0 is reserved
            for the empty tile and cannot be drawn on)
        pixels: List of {"x": int, "y": int, "color": "#RRGGBB"}
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if tile_index < 1:
        return "tile_index must be >= 1 (tile 0 is the reserved empty tile)"
    if not pixels:
        return "Pixels list cannot be empty"

    puts = []
    for pixel in pixels:
        rgb = _parse_hex_color(pixel.get("color", ""))
        if rgb is None:
            return f"Invalid color value: {pixel.get('color')}"
        r, g, b = rgb
        x = int(pixel.get("x", 0))
        y = int(pixel.get("y", 0))
        puts.append(
            f"        put(img, {x}, {y}, app.pixelColor.rgba({r}, {g}, {b}, 255))"
        )
    puts_lua = "\n".join(puts)

    safe_layer = lua_escape(layer_name)
    script = f"""
    {FIND_LAYER}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local target = find_layer(spr, "{safe_layer}")
    if not target then print("ERROR:Layer not found") return end
    if not target.isTilemap then print("ERROR:Layer is not a tilemap layer") return end

    local ts = target.tileset
    if not ts then print("ERROR:Layer has no tileset") return end

    local idx = {tile_index}
    if idx > #ts then print("ERROR:tile_index out of range (tileset has " .. (#ts - 1) .. " real tiles; pass " .. #ts .. " to append)") return end

    app.transaction(function()
        if idx == #ts then
            spr:newTile(ts)
        end
        local tile = ts:tile(idx)
        local img = tile.image:clone()
        local function put(im, x, y, color)
            if x >= 0 and y >= 0 and x < im.width and y < im.height then
                im:putPixel(x, y, color)
            end
        end
{puts_lua}
        tile.image = img
    end)

    spr:saveAs(spr.filename)
    print("OK")
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return (
            f"Drew {len(pixels)} pixels on tile {tile_index} of '{layer_name}' "
            f"in {filename}"
        )
    return f"Failed to draw on tile: {output}"


@mcp.tool()
async def set_tiles(
    filename: str,
    layer_name: str,
    frame_index: int,
    tiles: List[Dict[str, Any]],
) -> str:
    """Place tiles on a tilemap layer by grid position.

    Args:
        filename: Aseprite file to modify
        layer_name: Tilemap layer to edit
        frame_index: Frame index starting at 1
        tiles: List of {"col": int, "row": int, "tile_index": int}
            (col/row are grid coordinates; tile_index 0 clears the cell)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if not tiles:
        return "Tiles list cannot be empty"

    entries = []
    for t in tiles:
        entries.append(
            f"{{{int(t.get('col', 0))},{int(t.get('row', 0))},{int(t.get('tile_index', 0))}}}"
        )
    tiles_lua = ", ".join(entries)

    safe_layer = lua_escape(layer_name)
    script = f"""
    {FIND_LAYER}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then print("ERROR:Frame index out of range") return end

    local target = find_layer(spr, "{safe_layer}")
    if not target then print("ERROR:Layer not found") return end
    if not target.isTilemap then print("ERROR:Layer is not a tilemap layer") return end

    local ts = target.tileset
    local grid = spr.gridBounds
    local tw, th = grid.width, grid.height
    local cols = math.ceil(spr.width / tw)
    local rows = math.ceil(spr.height / th)

    local tiles = {{ {tiles_lua} }}
    for _, t in ipairs(tiles) do
        if t[1] < 0 or t[1] >= cols or t[2] < 0 or t[2] >= rows then
            print("ERROR:Tile position (" .. t[1] .. "," .. t[2] .. ") outside the " .. cols .. "x" .. rows .. " map")
            return
        end
        if t[3] < 0 or t[3] >= #ts then
            print("ERROR:tile_index " .. t[3] .. " out of range (tileset has " .. (#ts - 1) .. " real tiles)")
            return
        end
    end

    app.transaction(function()
        local frame = spr.frames[idx]
        local cel = target:cel(frame)
        local img
        if cel and cel.image.width == cols and cel.image.height == rows
           and cel.position.x == 0 and cel.position.y == 0 then
            img = cel.image
        else
            img = Image(cols, rows, ColorMode.TILEMAP)
            if cel then
                local old = cel.image
                local ox = cel.position.x // tw
                local oy = cel.position.y // th
                for y = 0, old.height - 1 do
                    for x = 0, old.width - 1 do
                        local nx, ny = x + ox, y + oy
                        if nx >= 0 and ny >= 0 and nx < cols and ny < rows then
                            img:putPixel(nx, ny, old:getPixel(x, y))
                        end
                    end
                end
            end
            cel = spr:newCel(target, frame, img, Point(0, 0))
        end
        for _, t in ipairs(tiles) do
            img:putPixel(t[1], t[2], t[3])
        end
        cel.image = img
    end)

    spr:saveAs(spr.filename)
    print("OK")
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return (
            f"Placed {len(tiles)} tiles on '{layer_name}' frame {frame_index} "
            f"in {filename}"
        )
    return f"Failed to set tiles: {output}"


@mcp.tool()
async def get_tile_at(
    filename: str,
    layer_name: str,
    frame_index: int,
    col: int,
    row: int,
) -> str:
    """Read which tile is placed at a grid position.

    Args:
        filename: Aseprite file to read
        layer_name: Tilemap layer to read
        frame_index: Frame index starting at 1
        col: Grid column (0-based)
        row: Grid row (0-based)

    Returns:
        JSON with {col, row, tile_index} (0 = empty).
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    safe_layer = lua_escape(layer_name)
    script = f"""
    {FIND_LAYER}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then print("ERROR:Frame index out of range") return end

    local target = find_layer(spr, "{safe_layer}")
    if not target then print("ERROR:Layer not found") return end
    if not target.isTilemap then print("ERROR:Layer is not a tilemap layer") return end

    local grid = spr.gridBounds
    local cel = target:cel(spr.frames[idx])
    local tile = 0
    if cel then
        local cx = {col} - cel.position.x // grid.width
        local cy = {row} - cel.position.y // grid.height
        if cx >= 0 and cy >= 0 and cx < cel.image.width and cy < cel.image.height then
            tile = app.pixelColor.tileI(cel.image:getPixel(cx, cy))
        end
    end
    print("TILE:" .. tile)
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if not success:
        return f"Failed to read tile: {output}"

    for line in output.splitlines():
        if line.startswith("TILE:"):
            return json.dumps({
                "col": col, "row": row, "tile_index": int(line[len("TILE:"):]),
            })
    return "No tile data returned"


@mcp.tool()
async def get_tilemap_info(filename: str, layer_name: str) -> str:
    """Get tilemap layer info: tile size, tile count, and map dimensions.

    Args:
        filename: Aseprite file to read
        layer_name: Tilemap layer to inspect

    Returns:
        JSON with tile_width, tile_height, tile_count (real tiles,
        excluding the empty tile 0), map_cols, map_rows.
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
    if not target.isTilemap then print("ERROR:Layer is not a tilemap layer") return end

    local ts = target.tileset
    local grid = spr.gridBounds
    print(string.format("INFO:%d,%d,%d,%d,%d",
        grid.width, grid.height, #ts - 1,
        math.ceil(spr.width / grid.width),
        math.ceil(spr.height / grid.height)))
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if not success:
        return f"Failed to get tilemap info: {output}"

    for line in output.splitlines():
        if line.startswith("INFO:"):
            tw, th, count, cols, rows = [int(v) for v in line[len("INFO:"):].split(",")]
            return json.dumps({
                "tile_width": tw, "tile_height": th, "tile_count": count,
                "map_cols": cols, "map_rows": rows,
            })
    return "No tilemap data returned"
