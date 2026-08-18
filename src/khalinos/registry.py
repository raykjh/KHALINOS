"""Application composition root for statically approved ToolPacks."""

from khalinos.browser_toolpack import BROWSER_PRODUCT_TOOLPACK
from khalinos.godot_toolpack import GODOT_TOPOLOGY_TOOLPACK
from khalinos.toolpacks import ToolPackRegistry


APPROVED_TOOLPACKS = ToolPackRegistry([
    BROWSER_PRODUCT_TOOLPACK,
    GODOT_TOPOLOGY_TOOLPACK,
])
DEFAULT_TOOLPACK_ID = BROWSER_PRODUCT_TOOLPACK.manifest.toolpack_id
