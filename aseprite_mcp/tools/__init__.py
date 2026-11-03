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
# Raw Lua is available by default for compatibility; deployments can hide it.
_ENABLE_RAW_LUA = os.getenv("ASEPRITE_ENABLE_RAW_LUA", "true").strip().lower()
if _ENABLE_RAW_LUA not in {"0", "false", "no", "off"}:
    from . import script
from . import text
from . import native_fx
from . import view
