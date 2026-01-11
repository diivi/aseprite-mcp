from .. import mcp

@mcp.tool()
async def animation_workflow_guide(use_case: str = "character") -> str:
    """Return a concise English guide for optimized animation workflows."""
    use_case = (use_case or "character").strip().lower()
    header = "Animation Workflow Guide"
    if use_case == "character":
        bullets = [
            "Block your key poses on frame 1, then copy the base with copy_frame/copy_cel.",
            "Use propagate_cels for static layers (body, clothing) across the range.",
            "Animate motion with tween_cel_positions or offset_cel_positions, avoid redrawing.",
            "Add secondary motion on separate layers (hair, accessories) for readability.",
            "Keep layers deterministic: set_layer + *_at drawing tools.",
            "Finalize with set_tag for loop ranges and export_sprite for preview.",
        ]
    elif use_case == "environment":
        bullets = [
            "Build the base scene once and copy with copy_sprite for variants.",
            "Use propagate_cels for static layers (sky, mountains, ground).",
            "Animate only the moving layers (clouds, birds, water) with tween/offset.",
            "Use apply_gradient_rect and palette tools for consistent color mood.",
            "Copy reusable assets across scenes with copy_layers_between_sprites.",
            "Tag loops and export GIFs to validate pacing.",
        ]
    else:
        bullets = [
            "Create the base on frame 1, then duplicate cels/frames for consistency.",
            "Animate by moving cels, not redrawing each frame.",
            "Use layer-targeted tools (*_at) to avoid active-cel drift.",
            "Propagate static layers across the frame range.",
            "Use tags for loop ranges and export previews early.",
        ]

    lines = [header, f"Use case: {use_case}"]
    lines.extend([f"- {b}" for b in bullets])
    return "\n".join(lines)
