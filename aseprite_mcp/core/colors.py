"""Shared hex-colour parsing for tool modules.

Accepts #RGB, #RGBA, #RRGGBB, #RRGGBBAA (with or without the leading '#')
and returns (r, g, b, a). Alpha defaults to 255 when not supplied. This is
the single source of truth that replaces the per-module _parse_hex_color
copies (which only handled #RRGGBB and hardcoded full alpha).
"""


def parse_hex_color(value: str) -> tuple[int, int, int, int] | None:
    """Parse a hex colour string into an (r, g, b, a) tuple, or None."""
    if not value:
        return None
    h = value.strip().lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    if len(h) not in (6, 8):
        return None
    try:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        a = int(h[6:8], 16) if len(h) == 8 else 255
    except ValueError:
        return None
    return r, g, b, a
