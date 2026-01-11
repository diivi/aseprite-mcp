import os
from ..core.commands import AsepriteCommand
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

    if os.path.exists(output_filename) and not overwrite:
        return f"Output file {output_filename} already exists"

    safe_path = output_filename.replace("\\", "/")
    script = f"""
    local spr = app.activeSprite
    if not spr then return "No active sprite" end

    spr:saveAs("{safe_path}")
    return "Sprite copied"
    """

    success, output = AsepriteCommand.execute_lua_script(script, filename)
    if success:
        return f"Sprite copied to {output_filename}"
    return f"Failed to copy sprite: {output}"
