#!/usr/bin/env bash
set -euo pipefail

# Optional: install Aseprite via Steam if credentials provided
if [[ -n "${STEAM_USERNAME:-}" && -n "${STEAM_PASSWORD:-}" ]]; then
  echo "[entrypoint] Installing Aseprite via SteamCMD..." >&2
  /app/scripts/install-aseprite-steam.sh || echo "[entrypoint] Steam install attempted. Proceeding..." >&2
fi

# If ASEPRITE_PATH not set but default path exists, set it
DEFAULT_ASE="${STEAM_INSTALL_DIR}/aseprite"
if [[ -z "${ASEPRITE_PATH:-}" && -x "$DEFAULT_ASE" ]]; then
  export ASEPRITE_PATH="$DEFAULT_ASE"
fi

# Show what will be used
echo "ASEPRITE_PATH=${ASEPRITE_PATH:-aseprite}" >&2

# Run the MCP server via uv
exec uv run -m aseprite_mcp
