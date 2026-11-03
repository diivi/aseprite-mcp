import os

from . import canvas
from . import drawing
from . import export
from . import animation
from . import preview
from . import palette
from . import scene
from . import guide
from . import quality
from . import pixel_read
from . import transform
from . import layers
from . import selection
from . import fx
from . import analysis
from . import slices
from . import tilemap
# Raw Lua runs with the host user's permissions, so require an explicit opt-in.
_ENABLE_RAW_LUA = os.getenv("ASEPRITE_ENABLE_RAW_LUA", "false").strip().lower()
if _ENABLE_RAW_LUA in {"1", "true", "yes", "on"}:
    from . import script
from . import text
from . import native_fx
from . import view
