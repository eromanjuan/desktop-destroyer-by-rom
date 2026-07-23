"""Tool registry.

The order here is the order shown in the toolbar and the order of the number-key
shortcuts. Drop a new Tool subclass into this list and it is fully wired up --
toolbar button, hotkey, cursor and all.
"""

import pygame

from .base import Tool, ToolContext
from .bomb import RemoteBomb
from .bow import Bow
from .bugs_tool import Bugs
from .flamethrower import Flamethrower
from .gasoline import Gasoline
from .grenade import Grenade
from .gun import Gun
from .hammer import Hammer
from .katana import Katana
from .missile import Missile
from .paintbrush import Paintbrush
from .rock import Rock
from .rpg import RPG
from .shuriken import Shuriken
from .washer import Washer

__all__ = ["Tool", "ToolContext", "build_tools", "Hammer", "Katana", "Shuriken",
           "Gun", "Bow", "Rock", "Grenade", "RPG", "RemoteBomb", "Gasoline",
           "Flamethrower", "Missile", "Bugs", "Paintbrush", "Washer"]

# Mnemonic letter keys, so they map to what a tool *is* rather than a slot
# number. Q (quit) and R (wash) are reserved by the app and stay off this list.
HOTKEYS = {
    "hammer": pygame.K_h, "katana": pygame.K_k, "shuriken": pygame.K_s,
    "gun": pygame.K_g, "bow": pygame.K_b, "rock": pygame.K_t,
    "grenade": pygame.K_n, "rpg": pygame.K_p, "bomb": pygame.K_m,
    "gasoline": pygame.K_l, "flame": pygame.K_f, "missile": pygame.K_u,
    "bug": pygame.K_i, "brush": pygame.K_a, "wash": pygame.K_w,
}


def build_tools() -> list[Tool]:
    tools = [Hammer(), Katana(), Shuriken(), Gun(), Bow(), Rock(),
             Grenade(), RPG(), RemoteBomb(), Gasoline(), Flamethrower(),
             Missile(), Bugs(), Paintbrush(), Washer()]
    for tool in tools:
        tool.key = HOTKEYS.get(tool.id)
    return tools
