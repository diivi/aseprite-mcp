# Aseprite MCP Tools

A Python module that serves as an MCP server for interacting with the Aseprite API

Demo where Cursor draws a cloud in aseprite using the MCP:

https://github.com/user-attachments/assets/572edf75-ab66-4700-87ee-d7d3d196c597

## Docker Usage

### Quick Start

Build and run the Docker image:
```bash
docker build -t aseprite-mcp:latest .
docker run -it --rm aseprite-mcp:latest
```

Or use the provided build scripts:
- **Linux/macOS**: `chmod +x build-docker.sh && ./build-docker.sh`
- **Windows**: `.\build-docker.ps1`

### Using Docker Compose
```bash
# Production
docker-compose up aseprite-mcp

# Development mode
docker-compose --profile dev up aseprite-mcp-dev
```

See [DOCKER.md](DOCKER.md) for detailed Docker setup instructions.

### Optional: Install Aseprite via Steam

To have the container install Aseprite via SteamCMD at startup, provide Steam credentials:

```powershell
# Create a .env with STEAM_USERNAME/STEAM_PASSWORD (and optional STEAM_GUARD_CODE)
# Then
docker run --rm -i --env-file .env aseprite-mcp:latest
```

If installed, the binary will be at `/opt/steamapps/common/Aseprite/aseprite` and `ASEPRITE_PATH` will be picked up automatically.

## Local Installation

### Prerequisites
- Python 3.13+
- `uv` package manager

### Installation:
```json
{
  "mcpServers": {
      "aseprite": {
          "command": "/opt/homebrew/bin/uv",
          "args": [
              "--directory",
              "/path/to/repo",
              "run",
              "-m",
              "aseprite_mcp"
          ]
      }
  }
}
```

## Enhanced Tools

This fork adds extra tools to improve animation and layer control:

- `set_frame(filename, frame_index)` - set the active frame (1-based)
- `set_frame_duration(filename, frame_index, duration_ms)` - set frame duration in ms
- `set_layer(filename, layer_name, create_if_missing)` - set or create an active layer
- `add_frames(filename, count, duration_ms)` - add multiple frames at once
- `set_frame_duration_all(filename, duration_ms)` - set duration for all frames
- `set_layer_visibility(filename, layer_name, visible)` - toggle layer visibility
- `set_layer_opacity(filename, layer_name, opacity)` - set layer opacity (0-255)
- `get_sprite_info(filename)` - return sprite info JSON string
- `start_preview_server(directory, port)` - start local HTTP server for previews
- `stop_preview_server(port)` - stop preview server
- `duplicate_frame_range(filename, start_frame, end_frame, times)` - append copies of a frame range
- `set_cel_position(filename, layer_name, frame_index, x, y, create_if_missing, source_frame_index)` - position a cel on a frame
- `tween_cel_positions(filename, layer_name, start_frame, end_frame, start_x, start_y, end_x, end_y, create_missing_cels, source_frame_index)` - linear position tween across frames
- `offset_cel_positions(filename, layer_name, start_frame, end_frame, dx, dy)` - shift cel positions across frames
- `create_cel(filename, layer_name, frame_index, x, y)` - create an empty cel at a position
- `clear_cel(filename, layer_name, frame_index)` - delete a cel on a frame
- `copy_cel(filename, layer_name, source_frame, target_frame, replace)` - copy a cel between frames
- `copy_frame(filename, source_frame, target_frame, overwrite)` - copy a frame (or append)
- `set_tag(filename, name, from_frame, to_frame, direction)` - create/update an animation tag (direction may be ignored in batch)
- `set_onion_skin(filename, enabled, before, after, opacity)` - configure onion skin (UI-only in batch)
- `propagate_cels(filename, layer_names, source_frame, start_frame, end_frame, replace)` - copy cels from a source frame to a frame range for layers
- `tween_cel_positions_eased(filename, layer_name, start_frame, end_frame, start_x, start_y, end_x, end_y, easing, create_missing_cels, source_frame_index)` - tween with easing (linear, ease_in, ease_out, ease_in_out, smoothstep)
- `tween_cel_opacity_eased(filename, layer_name, start_frame, end_frame, start_opacity, end_opacity, easing, create_missing_cels, source_frame_index)` - opacity tween with easing (linear, ease_in, ease_out, ease_in_out, smoothstep)
- `tween_cel_scale_eased(filename, layer_name, start_frame, end_frame, start_scale, end_scale, easing, anchor, replace, create_missing_cels, source_frame_index)` - scale tween with easing (linear, ease_in, ease_out, ease_in_out, smoothstep)
- `draw_pixels_at(filename, layer_name, frame_index, pixels, create_if_missing)` - draw pixels on a specific layer/frame
- `draw_line_at(filename, layer_name, frame_index, x1, y1, x2, y2, color, thickness, create_if_missing)` - draw a line on a specific layer/frame
- `draw_rectangle_at(filename, layer_name, frame_index, x, y, width, height, color, fill, create_if_missing)` - draw a rectangle on a specific layer/frame
- `draw_circle_at(filename, layer_name, frame_index, center_x, center_y, radius, color, fill, create_if_missing)` - draw a circle on a specific layer/frame
- `fill_area_at(filename, layer_name, frame_index, x, y, color, create_if_missing)` - fill an area on a specific layer/frame
- `draw_polygon(filename, layer_name, frame_index, points, color, fill, create_if_missing)` - draw a polygon on a specific layer/frame
- `draw_path(filename, layer_name, frame_index, points, color, thickness, create_if_missing)` - draw a polyline path on a specific layer/frame
- `apply_gradient_rect(filename, layer_name, frame_index, x, y, width, height, color_start, color_end, horizontal, create_if_missing)` - apply a linear gradient
- `get_palette(filename)` - get palette as JSON list
- `set_palette(filename, colors)` - set palette from hex list
- `remap_colors_in_cel_range(filename, layer_name, start_frame, end_frame, mappings, create_missing_cels, source_frame_index)` - remap colors in cels across a frame range
- `copy_sprite(filename, output_filename, overwrite)` - copy a sprite to a new .aseprite file
- `copy_layers_between_sprites(source_filename, target_filename, layer_names, replace, create_missing_frames)` - copy layers by name between sprites
- `animation_workflow_guide(use_case)` - return an English guide for optimized animation workflows
- `ensure_layers_present(filename, layer_names, start_frame, end_frame)` - ensure cels exist across frames
- `validate_scene(filename, required_layers, start_frame, end_frame)` - validate missing layers/cels (JSON)

## Animation Consistency Guide (for agents)
Use this workflow to avoid re-drawing every frame and keep consistent visuals:

1) Build the base scene once on frame 1 using layer-targeted tools (`*_at`) or `create_cel`.
2) Duplicate the base:
   - Same file: use `copy_frame` or `copy_cel` to populate other frames.
   - For static layers across many frames: use `propagate_cels`.
   - New file/scene: use `copy_sprite` to clone the whole scene, then adjust.
   - Cross-scene reuse: use `copy_layers_between_sprites` to reuse assets like trees or sky.
3) Animate via transforms, not redrawing:
   - `tween_cel_positions` for motion arcs
   - `offset_cel_positions` for subtle parallax/loop drift
4) Keep layers deterministic:
   - `set_layer` + layer-specific tools avoid active-cel drift.
5) For small variation, edit only a few frames or layers:
   - Use `clear_cel` + redraw on that layer/frame.

This minimizes token usage and preserves consistency across frames and scenes.

## Quality Checks
Run a validation pass before shipping animations:
```
python scripts/quality_check.py path/to/file.aseprite --layers sky,ground,character --start 1 --end 12
```
