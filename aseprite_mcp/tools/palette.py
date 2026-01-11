import os
from typing import List
from ..core.commands import AsepriteCommand
from .. import mcp

@mcp.tool()
async def get_palette(filename: str) -> str:
    """Get the active sprite palette as a JSON array of hex colors."""
    if not os.path.exists(filename):
        return f"File {filename} not found"

    script = """
    local spr = app.activeSprite
    if not spr then print("No active sprite") return end

    local ok, pal = pcall(function() return spr.palettes[1] end)
    if not ok or not pal then print("No palette") return end

    local parts = {}
    local size = #pal
    table.insert(parts, "[")
    for i = 0, size - 1 do
        local c = pal:getColor(i)
        local hex = string.format("#%02X%02X%02X", c.red, c.green, c.blue)
        table.insert(parts, "\\"" .. hex .. "\\"")
        if i < size - 1 then
            table.insert(parts, ",")
        end
    end
    table.insert(parts, "]")
    print(table.concat(parts))
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return output
    return f"Failed to get palette: {output}"

@mcp.tool()
async def set_palette(filename: str, colors: List[str]) -> str:
    """Set the active sprite palette using a list of hex colors."""
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if not colors:
        return "Colors list cannot be empty"

    rgb_list = []
    for color in colors:
        hex_color = color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        rgb_list.append((r, g, b))

    palette_entries = "\n".join(
        [f"    pal:setColor({i}, Color({r}, {g}, {b}))" for i, (r, g, b) in enumerate(rgb_list)]
    )

    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    local pal = Palette({len(rgb_list)})
{palette_entries}
    spr:setPalette(pal)
    spr:saveAs(spr.filename)
    return "Palette set"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Palette set with {len(colors)} colors in {filename}"
    return f"Failed to set palette: {output}"
