import glob
import os
from ..core.commands import AsepriteCommand, lua_escape, reject_traversal
from ..core.lua import FIND_LAYER, NORMALIZE_CEL
from .. import mcp

@mcp.tool()
async def export_sprite(filename: str, output_filename: str, format: str = "png") -> str:
    """Export the Aseprite file to another format.

    Args:
        filename: Name of the Aseprite file to export
        output_filename: Name of the output file
        format: Output format (default: "png", can be "png", "gif", "jpg", etc.)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    
    # Make sure format is lowercase
    format = format.lower()
    
    # Ensure output filename has the correct extension
    if not output_filename.lower().endswith(f".{format}"):
        output_filename = f"{output_filename}.{format}"
    
    # For animated exports
    if format == "gif":
        args = ["--batch", filename, "--save-as", output_filename]
        success, output = AsepriteCommand.run_command(args)
    else:
        # For still image exports
        args = ["--batch", filename, "--save-as", output_filename]
        success, output = AsepriteCommand.run_command(args)

    # Aseprite exits 0 even when it cannot write the requested format
    # (e.g. format="json"). Confirm a file actually appeared. A multi-frame
    # sprite saved to a still format produces frame-numbered siblings
    # (out1.png, out2.png, ...) instead of the exact name, so accept those
    # too — same convention as export_frame.
    if success:
        base, ext = os.path.splitext(output_filename)
        if not os.path.exists(output_filename) and not glob.glob(f"{base}*{ext}"):
            success = False
            output = "Aseprite exited 0 but wrote no file (the format may not be writable via --save-as)"

    if success:
        return f"Sprite exported successfully to {output_filename}"
    else:
        return f"Failed to export sprite: {output}"

@mcp.tool()
async def copy_sprite(filename: str, output_filename: str, overwrite: bool = False) -> str:
    """Copy a sprite to a new Aseprite file.

    Args:
        filename: Name of the Aseprite file to copy
        output_filename: Name of the output .aseprite file
        overwrite: Whether to overwrite if output exists
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"

    if not output_filename.lower().endswith(".aseprite"):
        output_filename = f"{output_filename}.aseprite"

    err = reject_traversal(output_filename)
    if err:
        return err

    if os.path.exists(output_filename) and not overwrite:
        return f"Output file {output_filename} already exists"

    safe_path = lua_escape(output_filename.replace("\\", "/"))
    script = f"""
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    spr:saveAs("{safe_path}")
    print("OK")
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success and not os.path.exists(output_filename):
        success = False
        output = "Aseprite exited 0 but wrote no file"
    if success:
        return f"Sprite copied to {output_filename}"
    return f"Failed to copy sprite: {output}"


@mcp.tool()
async def export_frame(
    filename: str,
    frame_index: int,
    output_filename: str,
    scale: int = 1,
) -> str:
    """Export a single frame as a PNG, optionally scaled up.

    Use this for visual feedback while drawing: export at scale 8-10 and
    open the PNG to inspect the result, then keep iterating.

    Args:
        filename: Aseprite file to export
        frame_index: Frame index starting at 1
        output_filename: Output PNG path
        scale: Integer nearest-neighbor scale factor (default 1)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if scale < 1 or scale > 64:
        return "scale must be between 1 and 64"
    err = reject_traversal(output_filename)
    if err:
        return err
    if not output_filename.lower().endswith(".png"):
        output_filename = f"{output_filename}.png"

    f0 = frame_index - 1  # CLI --frame-range is 0-based
    args = [
        "--batch", filename,
        "--frame-range", f"{f0},{f0}",
        "--scale", str(scale),
        "--save-as", output_filename,
    ]
    success, output = AsepriteCommand.run_command(args)
    if not success:
        return f"Failed to export frame: {output}"

    # With multi-frame sprites Aseprite may append the frame number to
    # the filename; rename the produced file when that happens.
    if not os.path.exists(output_filename):
        base, ext = os.path.splitext(output_filename)
        candidates = sorted(glob.glob(f"{base}*{ext}"))
        if candidates:
            os.replace(candidates[0], output_filename)
        else:
            return f"Export reported success but {output_filename} was not created"
    return f"Frame {frame_index} exported to {output_filename} at {scale}x"


@mcp.tool()
async def export_spritesheet(
    filename: str,
    output_filename: str,
    sheet_type: str = "horizontal",
    data_filename: str = "",
    scale: int = 1,
    padding: int = 0,
    tag_name: str = "",
) -> str:
    """Export frames as a sprite sheet, optionally with a JSON data file.

    Args:
        filename: Aseprite file to export
        output_filename: Output sheet image path (PNG)
        sheet_type: Layout: "horizontal", "vertical", "rows", "columns", or "packed"
        data_filename: Optional path for a JSON metadata file (json-array format)
        scale: Integer scale factor applied before packing (default 1)
        padding: Padding in pixels between frames (default 0)
        tag_name: Only include frames of this animation tag (default: all frames)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if sheet_type not in ("horizontal", "vertical", "rows", "columns", "packed"):
        return "sheet_type must be one of: horizontal, vertical, rows, columns, packed"
    if scale < 1 or scale > 64:
        return "scale must be between 1 and 64"
    if padding < 0:
        return "padding must be >= 0"
    err = reject_traversal(output_filename)
    if err:
        return err
    if not output_filename.lower().endswith(".png"):
        output_filename = f"{output_filename}.png"

    args = ["--batch"]
    if tag_name:
        # Frame filters only apply to --sheet when they appear before
        # the input file; resolve the tag to a 0-based --frame-range so
        # missing tags produce a clear error.
        safe_tag = lua_escape(tag_name)
        script = f"""
        local spr = app.activeSprite
        if not spr then print("ERROR:No active sprite") return end
        for _, tag in ipairs(spr.tags) do
            if tag.name == "{safe_tag}" then
                print("RANGE:" .. (tag.fromFrame.frameNumber - 1) .. "," .. (tag.toFrame.frameNumber - 1))
                return
            end
        end
        print("ERROR:Tag not found")
        """
        ok, out = AsepriteCommand.execute_lua_script_checked(script, filename)
        if not ok:
            return f"Failed to resolve tag: {out}"
        frame_range = next(
            (line[len("RANGE:"):] for line in out.splitlines() if line.startswith("RANGE:")),
            None,
        )
        if frame_range is None:
            return "Failed to resolve tag: no range returned"
        args += ["--frame-range", frame_range]
    args.append(filename)
    if scale > 1:
        args += ["--scale", str(scale)]
    args += ["--sheet-type", sheet_type]
    if padding > 0:
        args += ["--shape-padding", str(padding)]
    if data_filename:
        err = reject_traversal(data_filename)
        if err:
            return err
        args += ["--data", data_filename, "--format", "json-array"]
    args += ["--sheet", output_filename]

    success, output = AsepriteCommand.run_command(args)
    if success:
        msg = f"Sprite sheet exported to {output_filename} ({sheet_type})"
        if data_filename:
            msg += f" with data file {data_filename}"
        return msg
    return f"Failed to export sprite sheet: {output}"


@mcp.tool()
async def export_layers(
    filename: str,
    output_directory: str,
    include_hidden: bool = False,
) -> str:
    """Export each layer as its own PNG file named <layer>.png.

    Args:
        filename: Aseprite file to export
        output_directory: Directory for the per-layer PNGs (created if missing)
        include_hidden: Also export hidden layers (default False)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    err = reject_traversal(output_directory)
    if err:
        return err
    os.makedirs(output_directory, exist_ok=True)

    args = ["--batch"]
    if include_hidden:
        args.append("--all-layers")
    args += [
        "--split-layers", filename,
        "--save-as", os.path.join(output_directory, "{layer}.png"),
    ]
    success, output = AsepriteCommand.run_command(args)
    if success:
        produced = sorted(
            os.path.basename(p) for p in glob.glob(os.path.join(output_directory, "*.png"))
        )
        return f"Layers exported to {output_directory}: {', '.join(produced) or '(none)'}"
    return f"Failed to export layers: {output}"


@mcp.tool()
async def export_tag(
    filename: str,
    tag_name: str,
    output_filename: str,
    scale: int = 1,
) -> str:
    """Export the frames of an animation tag as a GIF or PNG sequence.

    Args:
        filename: Aseprite file to export
        tag_name: Animation tag to export
        output_filename: Output path; .gif gives an animation, .png a sequence
        scale: Integer scale factor (default 1)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if scale < 1 or scale > 64:
        return "scale must be between 1 and 64"
    err = reject_traversal(output_filename)
    if err:
        return err

    args = ["--batch", filename, "--tag", tag_name]
    if scale > 1:
        args += ["--scale", str(scale)]
    args += ["--save-as", output_filename]
    success, output = AsepriteCommand.run_command(args)
    if success:
        return f"Tag '{tag_name}' exported to {output_filename}"
    return f"Failed to export tag: {output}"


@mcp.tool()
async def import_image_as_layer(
    filename: str,
    image_path: str,
    layer_name: str,
    frame_index: int = 1,
    x: int = 0,
    y: int = 0,
) -> str:
    """Import an image file (PNG, etc.) into a layer of the sprite.

    Useful for bringing in reference images or composing pre-made parts.
    The layer is created if it does not exist. Works best when the sprite
    is in RGB color mode.

    Args:
        filename: Aseprite file to modify
        image_path: Image file to import
        layer_name: Layer to place the image on
        frame_index: Frame index starting at 1 (default 1)
        x: X position for the image's top-left corner (default 0)
        y: Y position for the image's top-left corner (default 0)
    """
    if not os.path.exists(filename):
        return f"File {filename} not found"
    if not os.path.exists(image_path):
        return f"Image {image_path} not found"

    safe_layer = lua_escape(layer_name)
    safe_image = lua_escape(os.path.abspath(image_path).replace("\\", "/"))
    script = f"""
    {FIND_LAYER}
    {NORMALIZE_CEL}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then print("ERROR:Frame index out of range") return end

    local src = Image{{ fromFile = "{safe_image}" }}
    if not src then print("ERROR:Could not load image") return end

    local target = find_layer(spr, "{safe_layer}")
    app.transaction(function()
        if not target then
            target = spr:newLayer()
            target.name = "{safe_layer}"
        end
        local cel = normalize_cel(spr, target, spr.frames[idx], true)
        cel.image:drawImage(src, Point({x}, {y}))
    end)

    spr:saveAs(spr.filename)
    print("OK")
    """

    success, output = AsepriteCommand.execute_lua_script_checked(script, filename)
    if success:
        return f"Image {image_path} imported onto '{layer_name}' frame {frame_index} in {filename}"
    return f"Failed to import image: {output}"
