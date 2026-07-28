"""Font loading and text rasterisation.

Aseprite's Lua API has no text drawing: there is no `Font` object and no
`Image:drawText`, and the GUI text tool is an editor state that scripts cannot
drive. Text therefore has to be rasterised here and blitted in as an image.

Two backends:

* **truetype** - any .ttf/.otf through Pillow. Rendered without antialiasing by
  default (grey coverage is thresholded to hard pixels), which is what pixel art
  wants; pass ``antialias=True`` to keep the soft edges.
* **bitmap** - a sprite-sheet font described by a ``font.json``. This covers game
  fonts whose glyphs are already pixels and must not be resampled. ``size`` acts
  as an integer scale factor.

Fonts live in ``~/.aseprite-mcp/fonts``: a bitmap font is a directory holding
``font.json`` plus its sheet PNGs, and a TrueType font is simply a ``.ttf``/
``.otf`` file dropped in. Installed system fonts are also discoverable.

font.json schema::

    {
      "name": "minecraft",
      "letter_gap": 1,          # px added after each glyph (advance: "ink" only)
      "space_width": 3,         # px advance for a glyph with no ink
      "sheets": [{
        "file": "ascii.png",
        "cell_w": 8, "cell_h": 8,
        "ascent": 7,            # rows from the cell top down to the baseline
        "origin": [0, 0],       # optional margin before the first cell
        "ink_rule": "alpha",    # "alpha" | "dark"
        "advance": "ink",       # "ink" | "box"
        "chars": ["ABC...", ...]  # one string per sheet row, left to right
      }],
      "overrides": {            # optional hand-drawn replacements, by codepoint
        "86": {"ascent": 7, "rows": ["#...#", ".#.#.", "..#.."]}
      }
    }

Sheets are consulted in order and the first one to claim a codepoint wins, so a
compact ASCII sheet can take precedence over a larger fallback. Each sheet keeps
its own ``ascent``, which is what lets sheets with different cell sizes share a
baseline.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = os.path.expanduser("~/.aseprite-mcp/fonts")

_SYSTEM_FONT_DIRS = (
    "/System/Library/Fonts",
    "/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
    "C:/Windows/Fonts",
)

_TTF_EXT = (".ttf", ".otf", ".ttc")

Point = tuple[int, int]


class FontError(Exception):
    """Raised for an unknown font, a malformed descriptor, or a bad size."""


@dataclass
class Glyph:
    """A rasterised glyph.

    `ink` holds (x, y) offsets from the glyph's top-left; `ascent` is how far
    that top sits above the baseline.
    """

    ink: set[Point] = field(default_factory=set)
    advance: int = 0
    ascent: int = 0
    height: int = 0


# ---------------------------------------------------------------------------
# bitmap sheet fonts
# ---------------------------------------------------------------------------


class BitmapFont:
    """Sprite-sheet font laid out on a fixed cell grid."""

    is_bitmap = True

    def __init__(self, path: str):
        descriptor = os.path.join(path, "font.json")
        try:
            with open(descriptor, encoding="utf-8") as fh:
                spec = json.load(fh)
        except (OSError, ValueError) as exc:
            raise FontError(f"Could not read {descriptor}: {exc}") from exc

        self.name = spec.get("name", os.path.basename(path))
        self.letter_gap = int(spec.get("letter_gap", 1))
        self.space_width = int(spec.get("space_width", 3))
        self._cache: dict[int, Glyph | None] = {}
        self._sheets: list[dict] = []
        self._index: dict[int, tuple[int, int, int]] = {}

        for sheet in spec.get("sheets") or ():
            try:
                image = Image.open(os.path.join(path, sheet["file"])).convert("RGBA")
            except (OSError, KeyError) as exc:
                raise FontError(f"Bad sheet in {descriptor}: {exc}") from exc
            self._sheets.append({
                "px": image.load(),
                "size": image.size,
                "cell_w": int(sheet["cell_w"]),
                "cell_h": int(sheet["cell_h"]),
                "ascent": int(sheet["ascent"]),
                "origin": tuple(sheet.get("origin", (0, 0))),
                # "alpha": a transparent pixel is empty and the cell is the glyph
                #          box (Minecraft-style sheets).
                # "dark":  an opaque white background delimits the glyph box and
                #          dark pixels are the ink (Aseprite's own sheets).
                "ink_rule": sheet.get("ink_rule", "alpha"),
                # "ink": advance is the ink extent plus letter_gap.
                # "box": advance is the glyph box width, which already carries
                #        the font's own side bearing.
                "advance": sheet.get("advance", "ink"),
            })
            index = len(self._sheets) - 1
            for row, line in enumerate(sheet.get("chars") or ()):
                for col, char in enumerate(line):
                    codepoint = ord(char)
                    if codepoint and codepoint not in self._index:
                        self._index[codepoint] = (index, row, col)

        if not self._sheets:
            raise FontError(f"{descriptor} declares no sheets")

        self._overrides = {
            int(key): _glyph_from_rows(entry["rows"], entry.get("ascent"), self.letter_gap)
            for key, entry in (spec.get("overrides") or {}).items()
        }

    def glyph(self, codepoint: int) -> Glyph | None:
        if codepoint in self._cache:
            return self._cache[codepoint]

        glyph = self._overrides.get(codepoint)
        if glyph is None:
            location = self._index.get(codepoint)
            if location is None:
                self._cache[codepoint] = None
                return None
            glyph = self._read_cell(*location)

        self._cache[codepoint] = glyph
        return glyph

    def _read_cell(self, sheet_index: int, row: int, col: int) -> Glyph:
        sheet = self._sheets[sheet_index]
        px = sheet["px"]
        cell_w, cell_h = sheet["cell_w"], sheet["cell_h"]
        sheet_w, sheet_h = sheet["size"]
        ox = sheet["origin"][0] + col * cell_w
        oy = sheet["origin"][1] + row * cell_h
        dark = sheet["ink_rule"] == "dark"

        def is_background(x: int, y: int) -> bool:
            pixel = px[x, y]
            return pixel[3] == 255 and pixel[0] == 255 and pixel[1] == 255 and pixel[2] == 255

        box_w, box_h = cell_w, cell_h
        if dark:
            # The box runs from the cell origin until the white sheet background.
            box_w = 0
            while box_w < cell_w and ox + box_w < sheet_w and not is_background(ox + box_w, oy):
                box_w += 1
            box_h = 0
            while box_h < cell_h and oy + box_h < sheet_h and not is_background(ox, oy + box_h):
                box_h += 1

        ink: set[Point] = set()
        ink_width = 0
        for y in range(box_h):
            for x in range(box_w):
                pixel = px[ox + x, oy + y]
                lit = (
                    pixel[3] > 0 and max(pixel[0], pixel[1], pixel[2]) < 128
                    if dark
                    else pixel[3] > 0
                )
                if lit:
                    ink.add((x, y))
                    ink_width = max(ink_width, x + 1)

        if sheet["advance"] == "box":
            advance = box_w or self.space_width
        else:
            advance = (ink_width or self.space_width) + self.letter_gap
        return Glyph(ink=ink, advance=advance, ascent=sheet["ascent"], height=box_h)

    def layout(self, text: str, scale: int, letter_spacing: int) -> tuple[set[Point], int]:
        """Rasterise `text`; x runs from the pen origin, y from the baseline."""
        ink: set[Point] = set()
        pen = 0
        for char in text:
            glyph = self.glyph(ord(char))
            if glyph is None:
                continue
            for gx, gy in glyph.ink:
                base_x = pen + gx * scale
                base_y = (gy - glyph.ascent) * scale
                for dy in range(scale):
                    for dx in range(scale):
                        ink.add((base_x + dx, base_y + dy))
            pen += glyph.advance * scale + letter_spacing
        return ink, max(0, pen - letter_spacing)


def _glyph_from_rows(rows: list[str], ascent: int | None, letter_gap: int) -> Glyph:
    """Build a glyph from `#`-and-`.` rows, as used by font.json overrides."""
    ink: set[Point] = set()
    width = 0
    for y, line in enumerate(rows):
        for x, char in enumerate(line):
            if char not in (".", " "):
                ink.add((x, y))
                width = max(width, x + 1)
    return Glyph(
        ink=ink,
        advance=width + letter_gap,
        ascent=len(rows) if ascent is None else ascent,
        height=len(rows),
    )


# ---------------------------------------------------------------------------
# truetype fonts
# ---------------------------------------------------------------------------


class TrueTypeFont:
    is_bitmap = False

    def __init__(self, path: str):
        self.path = path
        self.name = os.path.splitext(os.path.basename(path))[0]

    def layout(
        self,
        text: str,
        size: int,
        letter_spacing: int,
        antialias: bool = False,
        threshold: int = 128,
    ) -> tuple[set[Point], int]:
        try:
            font = ImageFont.truetype(self.path, size)
        except OSError as exc:
            raise FontError(f"Could not load font {self.path}: {exc}") from exc

        if not letter_spacing:
            return self._raster(font, text, antialias, threshold)

        # Per-character placement so the extra spacing can be injected.
        ink: set[Point] = set()
        pen = 0
        for char in text:
            glyph_ink, advance = self._raster(font, char, antialias, threshold)
            ink |= {(x + pen, y) for x, y in glyph_ink}
            pen += advance + letter_spacing
        return ink, max(0, pen - letter_spacing)

    @staticmethod
    def _raster(font, text: str, antialias: bool, threshold: int) -> tuple[set[Point], int]:
        """Rasterise `text`; x runs from the pen origin, y from the baseline."""
        ascent, descent = font.getmetrics()
        advance = int(round(font.getlength(text)))
        box = font.getbbox(text)
        # Glyphs can overhang the advance on either side (italics, accents,
        # negative bearings), so leave room around the drawn string.
        pad = max(8, int(getattr(font, "size", 0) or 0))
        width = max(1, max(box[2], advance) + pad * 2)
        height = max(1, ascent + descent + pad * 2)

        canvas = Image.new("L", (width, height), 0)
        ImageDraw.Draw(canvas).text((pad, pad), text, font=font, fill=255)
        px = canvas.load()

        cutoff = 1 if antialias else threshold
        ink = {
            (x - pad, y - pad - ascent)
            for y in range(height)
            for x in range(width)
            if px[x, y] >= cutoff
        }
        return ink, advance


# ---------------------------------------------------------------------------
# discovery and resolution
# ---------------------------------------------------------------------------


def _iter_user_fonts():
    if not os.path.isdir(FONT_DIR):
        return
    for entry in sorted(os.listdir(FONT_DIR)):
        full = os.path.join(FONT_DIR, entry)
        if os.path.isdir(full) and os.path.exists(os.path.join(full, "font.json")):
            yield entry, full, "bitmap"
        elif entry.lower().endswith(_TTF_EXT):
            yield os.path.splitext(entry)[0], full, "truetype"


def _iter_system_fonts():
    for directory in _SYSTEM_FONT_DIRS:
        if not os.path.isdir(directory):
            continue
        try:
            entries = sorted(os.listdir(directory))
        except OSError:
            continue
        for entry in entries:
            if entry.lower().endswith(_TTF_EXT):
                yield os.path.splitext(entry)[0], os.path.join(directory, entry), "truetype"


def available_fonts() -> list[dict]:
    """User fonts first, then system fonts, de-duplicated by name."""
    seen: set[str] = set()
    found: list[dict] = []
    for source, iterator in (("user", _iter_user_fonts()), ("system", _iter_system_fonts())):
        for name, path, kind in iterator:
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            found.append({"name": name, "kind": kind, "path": path, "source": source})
    return found


_loaded: dict[str, BitmapFont | TrueTypeFont] = {}


def load_font(spec: str) -> BitmapFont | TrueTypeFont:
    """Resolve a font by name, or by path to a font file/bitmap font directory."""
    if spec in _loaded:
        return _loaded[spec]

    path: str | None = None
    kind: str | None = None

    if os.path.sep in spec or spec.lower().endswith(_TTF_EXT):
        expanded = os.path.expanduser(spec)
        if os.path.isdir(expanded) and os.path.exists(os.path.join(expanded, "font.json")):
            path, kind = expanded, "bitmap"
        elif os.path.isfile(expanded):
            path, kind = expanded, "truetype"

    if path is None:
        for entry in available_fonts():
            if entry["name"].lower() == spec.lower():
                path, kind = entry["path"], entry["kind"]
                break

    if path is None:
        raise FontError(
            f"Font '{spec}' not found. Call list_text_fonts to see what is available, "
            f"or pass a path to a .ttf/.otf file or to a bitmap font directory."
        )

    font = BitmapFont(path) if kind == "bitmap" else TrueTypeFont(path)
    _loaded[spec] = font
    return font


def clear_cache() -> None:
    """Forget resolved fonts so edited descriptors are picked up again."""
    _loaded.clear()


# ---------------------------------------------------------------------------
# shaping
# ---------------------------------------------------------------------------


def _dilate(ink: set[Point], passes: int) -> set[Point]:
    """Faux bold: grow right and down, which keeps counters open."""
    for _ in range(passes):
        ink = ink | {(x + 1, y) for x, y in ink} | {(x, y + 1) for x, y in ink}
    return ink


def shape(
    text: str,
    font: BitmapFont | TrueTypeFont,
    size: int = 1,
    letter_spacing: int = 0,
    bold: int = 0,
    antialias: bool = False,
    threshold: int = 128,
) -> tuple[set[Point], dict]:
    """Rasterise `text` and report its metrics.

    Returns (ink, metrics). Ink coordinates run from the pen origin on x and
    from the baseline on y, so anything above the baseline is negative.
    """
    if bold < 0:
        raise FontError("bold must be >= 0")

    if font.is_bitmap:
        if size < 1:
            raise FontError("size is an integer scale factor for bitmap fonts; must be >= 1")
        ink, advance = font.layout(text, size, letter_spacing)
    else:
        if size < 1:
            raise FontError("size is a pixel height for TrueType fonts; must be >= 1")
        ink, advance = font.layout(text, size, letter_spacing, antialias, threshold)

    if bold:
        ink = _dilate(ink, bold)

    if not ink:
        return ink, {
            "advance_width": advance,
            "width": 0,
            "height": 0,
            "left": 0,
            "top": 0,
            "bottom": 0,
        }

    xs = [x for x, _ in ink]
    ys = [y for _, y in ink]
    return ink, {
        "advance_width": advance + bold,
        "width": max(xs) - min(xs) + 1,
        "height": max(ys) - min(ys) + 1,
        "left": min(xs),
        "top": min(ys),
        "bottom": max(ys),
    }
