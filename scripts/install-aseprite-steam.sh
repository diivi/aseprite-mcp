#!/usr/bin/env bash
set -euo pipefail

# This script installs Aseprite via SteamCMD if STEAM_USERNAME/STEAM_PASSWORD are provided.
# Environment variables:
#   STEAM_USERNAME, STEAM_PASSWORD[, STEAM_GUARD_CODE]
#   STEAM_APPID (default 431730)
#   STEAM_INSTALL_DIR (default /opt/steamapps/common/Aseprite)
# Result:
#   Exports ASEPRITE_PATH=/opt/steamapps/common/Aseprite/aseprite

: "${STEAM_APPID:=431730}"
: "${STEAM_INSTALL_DIR:=/opt/steamapps/common/Aseprite}"

if [[ -z "${STEAM_USERNAME:-}" || -z "${STEAM_PASSWORD:-}" ]]; then
  echo "[install-aseprite-steam] No Steam credentials provided; skipping install." >&2
  exit 0
fi

mkdir -p "${STEAM_INSTALL_DIR}"
# steamcmd path on Ubuntu images
STEAMCMD_BIN="/usr/games/steamcmd"
if [[ ! -x "$STEAMCMD_BIN" ]]; then
  echo "[install-aseprite-steam] steamcmd not found at $STEAMCMD_BIN" >&2
  exit 1
fi

LOGIN_ARGS=("+login" "$STEAM_USERNAME" "$STEAM_PASSWORD")
if [[ -n "${STEAM_GUARD_CODE:-}" ]]; then
  LOGIN_ARGS=("+set_steam_guard_code" "$STEAM_GUARD_CODE" "${LOGIN_ARGS[@]}")
fi

# Use anonymous if credentials fail? We require credentials for paid app.
set +e
"$STEAMCMD_BIN" +force_install_dir "$STEAM_INSTALL_DIR" \
  "${LOGIN_ARGS[@]}" \
  +app_update "$STEAM_APPID" validate \
  +quit >&2
STATUS=$?
set -e
if [[ $STATUS -ne 0 ]]; then
  echo "[install-aseprite-steam] steamcmd failed with status $STATUS" >&2
  exit $STATUS
fi

ASE_BIN_CANDIDATE="${STEAM_INSTALL_DIR}/aseprite"
if [[ -x "$ASE_BIN_CANDIDATE" ]]; then
  echo "export ASEPRITE_PATH=\"$ASE_BIN_CANDIDATE\"" >> /etc/profile.d/aseprite.sh
  echo "ASEPRITE_PATH set to $ASE_BIN_CANDIDATE" >&2
else
  echo "[install-aseprite-steam] Could not locate aseprite binary at $ASE_BIN_CANDIDATE" >&2
  exit 1
fi
