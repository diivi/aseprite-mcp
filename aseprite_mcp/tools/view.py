import functools
import io
import json
import math
import os
import struct
import tempfile

from mcp.server.fastmcp import Image
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont

from ..core.commands import AsepriteCommand, reject_traversal
from .. import mcp

MAX_FRAMES = 16
MAX_COLUMNS = 4
TARGET_FRAME_PX = 384  # auto scale aims for frames about this big
MAX_SHEET_PX = 1568    # larger images get downscaled by the client, blurring pixels
MAX_EXPLICIT_PX = 8192  # hard cap when the caller picks the scale
RULER_W = 30
RULER_H = 18
TITLE_H = 18
GAP = 16

CHECKER = ((236, 236, 236, 255), (250, 250, 250, 255))
MINOR_LINE = (0, 0, 0, 38)
MAJOR_LINE = (0, 0, 0, 110)
LABEL = (90, 90, 90, 255)
TITLE = (30, 30, 30, 255)


@functools.cache
def _font(size: int):
    return ImageFont.load_default(size=size)


def _frame_count(filename: str) -> int | None:
    """Read the frame count from the .aseprite header, or None for other files."""
    try:
        with open(filename, "rb") as f:
            header = f.read(8)
    except OSError:
        return None
    if len(header) < 8:
        return None
    _, magic, frames = struct.unpack("<IHH", header)
    return frames if magic == 0xA5E0 else None


def _parse_frames(frames: str, total: int) -> list[int] | str:
    """Parse "", "3", "1-4" or "1,3,6-8" into 1-based frame numbers."""
    if not frames.strip():
        return list(range(1, min(total, MAX_FRAMES) + 1))
    picked = []
    for part in frames.split(","):
        part = part.strip()
        try:
            a, b = (int(v) for v in part.split("-", 1)) if "-" in part else (int(part), int(part))
        except ValueError:
            return f"Invalid frames '{frames}': use e.g. \"3\", \"1-4\" or \"1,3,6-8\""
        if a > b:
            return f"Invalid range '{part}': the first frame must not be after the last"
        for f in (a, b):
            if f < 1 or f > total:
                return f"Frame {f} out of range (sprite has {total} frames)"
        if len(picked) + (b - a + 1) > MAX_FRAMES:
            return f"Too many frames; show at most {MAX_FRAMES} at a time, e.g. frames=\"1-{MAX_FRAMES}\""
        picked.extend(range(a, b + 1))
    return list(dict.fromkeys(picked))


def _spans(picked: list[int]) -> list[tuple[int, int]]:
    """Group frame numbers into contiguous (first, last) spans, in order."""
    spans = []
    for n in sorted(picked):
        if spans and n == spans[-1][1] + 1:
            spans[-1] = (spans[-1][0], n)
        else:
            spans.append((n, n))
    return spans


def _export(filename: str, layer_name: str, span: tuple[int, int] | None, tmp: str):
    """Render frames with the Aseprite CLI; returns (frames by number, layer list) or an error string."""
    sheet_path = os.path.join(tmp, "sheet.png")
    data_path = os.path.join(tmp, "sheet.json")
    args = ["--batch"]
    if layer_name:
        args += ["--layer", layer_name]
    if span:
        args += ["--frame-range", f"{span[0] - 1},{span[1] - 1}"]
    args += [
        filename,
        "--sheet", sheet_path, "--sheet-type", "horizontal",
        "--data", data_path, "--format", "json-array", "--list-layers",
    ]
    success, output = AsepriteCommand.run_command(args)
    if not success:
        return f"Failed to render sprite: {output}"
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)
    with PILImage.open(sheet_path) as im:
        sheet = im.convert("RGBA")
    first = span[0] if span else 1
    frames = {}
    for i, entry in enumerate(data["frames"]):
        r = entry["frame"]
        frames[first + i] = (sheet.crop((r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"])), entry["duration"])
    return frames, data["meta"].get("layers", [])


def _label_step(scale: int) -> int:
    """Smallest ruler step whose labels do not collide at this scale."""
    for step in (1, 2, 4, 8, 16, 32, 64):
        if step * scale >= 22:
            return step
    return 128


def _checker(w: int, h: int) -> PILImage.Image:
    """A 1-pixel checkerboard, built from two row patterns instead of pixel by pixel."""
    a, b = bytes(CHECKER[0]), bytes(CHECKER[1])
    even = ((a + b) * (w // 2 + 1))[: w * 4]
    odd = ((b + a) * (w // 2 + 1))[: w * 4]
    data = ((even + odd) * (h // 2 + 1))[: w * h * 4]
    return PILImage.frombytes("RGBA", (w, h), data)


def _render_frame(frame: PILImage.Image, checker: PILImage.Image, scale: int, grid: bool) -> PILImage.Image:
    w, h = frame.size
    out = PILImage.alpha_composite(checker, frame)
    out = out.resize((w * scale, h * scale), PILImage.NEAREST)
    if grid and scale >= 4:
        lines = PILImage.new("RGBA", out.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lines)
        for x in range(1, w):
            d.line([(x * scale, 0), (x * scale, h * scale)], fill=MAJOR_LINE if x % 8 == 0 else MINOR_LINE)
        for y in range(1, h):
            d.line([(0, y * scale), (w * scale, y * scale)], fill=MAJOR_LINE if y % 8 == 0 else MINOR_LINE)
        out = PILImage.alpha_composite(out, lines)
    return out


def _panel(frame: PILImage.Image, checker: PILImage.Image, title: str, scale: int, grid: bool, rulers: bool) -> PILImage.Image:
    """One frame with a title above it and coordinate rulers on the top and left."""
    w, h = frame.size
    body = _render_frame(frame, checker, scale, grid)
    left, top = _margins(rulers)
    panel = PILImage.new("RGBA", (left + body.width, top + body.height), (255, 255, 255, 255))
    panel.paste(body, (left, top))
    d = ImageDraw.Draw(panel)
    d.text((left, 2), title, fill=TITLE, font=_font(13))
    if rulers:
        font = _font(11)
        step = _label_step(scale)
        for x in range(0, w, step):
            cx = left + x * scale + scale // 2
            d.text((cx, top - 3), str(x), fill=LABEL, font=font, anchor="mb")
        for y in range(0, h, step):
            cy = top + y * scale + scale // 2
            d.text((left - 4, cy), str(y), fill=LABEL, font=font, anchor="rm")
    return panel


def _margins(rulers: bool) -> tuple[int, int]:
    return (RULER_W if rulers else 0), TITLE_H + (RULER_H if rulers else 0)


def _sheet_size(fw: int, fh: int, scale: int, cols: int, rows: int, rulers: bool) -> tuple[int, int]:
    left, top = _margins(rulers)
    pw, ph = left + fw * scale, top + fh * scale
    return cols * pw + (cols + 1) * GAP, rows * ph + (rows + 1) * GAP


@mcp.tool()
async def view_sprite(
    filename: str,
    frames: str = "",
    layer_name: str = "",
    scale: int = 0,
    grid: bool = True,
    rulers: bool = True,
    output_filename: str = "",
):
    """Look at the sprite: returns an image of its frames that you can see directly.

    Use this after every drawing pass instead of exporting a PNG and opening
    it. Each frame is scaled up with nearest-neighbour, shown over a light
    checkerboard (transparent pixels), with a pixel grid (darker every 8 px)
    and rulers giving sprite coordinates, so a mistake you spot can be fixed
    at exact x/y right away. Frames are laid out side by side, at most four
    per row, each titled with its number and duration.

    Args:
        filename: Aseprite file to look at
        frames: Frames to show, 1-based: "3", "1-4" or "1,3,6-8", at most 16;
            "" shows all frames (the first 16 of longer sprites)
        layer_name: Show only this layer, by name or "group/layer" path
            (default: all visible layers)
        scale: Zoom factor, 1-64; 0 picks one so each frame is ~384 px
        grid: Draw the pixel grid (only when the scale is 4 or more)
        rulers: Label x across the top and y down the left
        output_filename: Optional path to also save the image as PNG
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if scale < 0 or scale > 64:
        return "scale must be between 0 (auto) and 64"
    if output_filename:
        err = reject_traversal(output_filename)
        if err:
            return err

    # Validate the frames before rendering, then render only the spans they cover.
    total = _frame_count(filename)
    picked = _parse_frames(frames, total) if total else None
    if isinstance(picked, str):
        return picked

    rendered, layers = {}, []
    with tempfile.TemporaryDirectory() as tmp:
        for span in _spans(picked) if picked else [None]:
            result = _export(filename, layer_name, span, tmp)
            if isinstance(result, str):
                return result
            rendered.update(result[0])
            layers = result[1]

    # With --layer, Aseprite lists only the layers that matched the name.
    if layer_name and not layers:
        return f"Layer '{layer_name}' not found"

    if picked is None:  # not an .aseprite file: everything was rendered, validate now
        total = len(rendered)
        picked = _parse_frames(frames, total)
        if isinstance(picked, str):
            return picked

    fw, fh = rendered[picked[0]][0].size
    cols = min(len(picked), MAX_COLUMNS)
    rows = math.ceil(len(picked) / cols)
    if scale == 0:
        scale = max(1, TARGET_FRAME_PX // max(fw, fh))
        while scale > 1 and max(_sheet_size(fw, fh, scale, cols, rows, rulers)) > MAX_SHEET_PX:
            scale -= 1
    elif max(_sheet_size(fw, fh, scale, cols, rows, rulers)) > MAX_EXPLICIT_PX:
        return (f"Image would be larger than {MAX_EXPLICIT_PX} px at {scale}x; "
                f"use a smaller scale, fewer frames, or scale=0 to pick one")

    checker = _checker(fw, fh)
    panels = []
    for n in picked:
        frame, duration = rendered[n]
        panels.append(_panel(frame, checker, f"frame {n} · {duration}ms", scale, grid, rulers))

    pw, ph = panels[0].size
    out = PILImage.new("RGB", _sheet_size(fw, fh, scale, cols, rows, rulers), (255, 255, 255))
    for i, p in enumerate(panels):
        out.paste(p, (GAP + (i % cols) * (pw + GAP), GAP + (i // cols) * (ph + GAP)))

    shown = ", ".join(str(n) for n in picked)
    text = (
        f"{os.path.basename(filename)}: {fw}x{fh}, {total} frame(s); "
        f"showing frame(s) {shown}{f' of layer {layer_name}' if layer_name else ''} at {scale}x. "
        f"Rulers give sprite coordinates (x across the top, y down the left)."
    )
    if max(out.size) > MAX_SHEET_PX:
        text += f" The image is {out.width}x{out.height} and may be shrunk on your side; ask for fewer frames to see every pixel."
    if output_filename:
        if not output_filename.lower().endswith(".png"):
            output_filename = f"{output_filename}.png"
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_filename)), exist_ok=True)
            out.save(output_filename)
            text += f" Saved to {output_filename}."
        except OSError as e:
            text += f" Could not save to {output_filename}: {e}."

    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return [text, Image(data=buf.getvalue(), format="png")]
