"""Aseprite MCP - Model Context Protocol implementation for Aseprite."""

from mcp.server.fastmcp import FastMCP


INSTRUCTIONS = """\
Tools for drawing and animating pixel art in Aseprite. Sprites are small (16-64 px): work in passes \
and check each one.

1. Plan: write down the pixel box of each part (head, torso, legs, weapon) first; leave a 1-2 px margin.
2. Silhouette in one flat color. Use shape tools (draw_line_at, draw_ellipse_at, fill_area_at) for big \
forms and draw_pixels_at for details. Clean edges: equal steps on straight diagonals (1-1-1, 2-2-2), \
gradual steps on curves (1,2,3 not 1,3,1), no L-shaped doubles on 1 px lines, no lone pixels.
3. Palette before color: one generate_color_ramp (steps=3-4) per material, 8-16 colors in total. \
Neighbouring materials must differ in lightness, not just hue.
4. Flats, then shade from one light (top-left): highlight on the lit side, shadow on the far side and \
under overhangs (chin, arms). Pillow shading (light center, dark ring at the edge) is wrong. \
No dithering or anti-aliasing on sprites under 32 px.
5. Outline in one dark color (darkest ramp step or near-black), never lighter than the fill \
(selective outlines only on larger sprites). outline_cel adds 1 px outside the shape.
6. After every pass: export_frame at scale 8 and view the PNG, and run get_color_stats to catch stray \
colors. Fix before going on. If it does not read, change the shape, not the details.

Animate pose to pose: redraw each key pose (anticipation, action, follow-through) on its own frame, \
with the whole body involved and the feet on one ground line unless airborne. copy_frame, \
erase_region the part that moves, then redraw it. Tween or offset cels only for rigid objects and \
secondary motion, never as the main motion. Call animation_workflow_guide before animating.
"""

mcp = FastMCP("aseprite", instructions=INSTRUCTIONS)

__version__ = "0.1.0"
__author__ = "Divyansh Singh"
