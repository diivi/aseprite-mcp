"""Shared wrapper for native Aseprite `app.command.*` filters.

Native engine commands act on the ACTIVE sprite / layer / frame (and the
active selection for region scope), NOT on explicit arguments — so the
wrapper resolves + activates the target BEFORE the command, error-first,
or a filter silently hits the wrong layer. Verified headless under
`--batch` with `{ui=false}` (T0, 2026-06-18).
"""
from .lua import FIND_LAYER
from .commands import lua_escape


def build_native_command_script(
    command_lua: str,
    layer_name: str = "",
    frame_index: int = 1,
    region: tuple[int, int, int, int] | None = None,
) -> str:
    """Wrap an `app.command.X{ui=false,...}` snippet with target activation,
    an optional selection scope, a transaction, save, and the ERROR:/OK
    protocol used by the checked-execution path.

    Args:
        command_lua: the `app.command.X{ui=false, ...}` Lua line(s)
        layer_name: layer to activate first (empty = leave active layer)
        frame_index: 1-based frame to activate
        region: optional (x, y, w, h) to scope the command via a selection
    """
    safe_layer = lua_escape(layer_name)
    if region is not None:
        x, y, w, h = region
        sel_set = f"spr.selection = Selection(Rectangle({x}, {y}, {w}, {h}))"
        sel_clear = "spr.selection:deselect()"
    else:
        sel_set = sel_clear = ""
    return f"""
    {FIND_LAYER}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end
    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then print("ERROR:Frame index out of range") return end
    app.activeFrame = spr.frames[idx]
    if "{safe_layer}" ~= "" then
        local target = find_layer(spr, "{safe_layer}")
        if not target then print("ERROR:Layer not found") return end
        app.activeLayer = target
    end
    {sel_set}
    app.transaction(function()
{command_lua}
    end)
    {sel_clear}
    spr:saveAs(spr.filename)
    print("OK")
    """
