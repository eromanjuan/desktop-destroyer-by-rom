"""Tool registry.

The order here is the order shown in the toolbar and the order of the number-key
shortcuts. Drop a new Tool subclass into this list and it is fully wired up --
toolbar button, hotkey, cursor and all.
"""

import pygame

from .base import Tool, ToolContext
from .bomb import RemoteBomb
from .bow import Bow
from .flamethrower import Flamethrower
from .gasoline import Gasoline
from .grenade import Grenade
from .gun import Gun
from .hammer import Hammer
from .katana import Katana
from .missile import Missile
from .paintbrush import Paintbrush
from .rock import Rock
from .washer import Washer

__all__ = ["Tool", "ToolContext", "build_tools", "Hammer", "Katana", "Gun",
           "Bow", "Rock", "Grenade", "RemoteBomb", "Gasoline", "Flamethrower",
           "Missile", "Paintbrush", "Washer"]

# 1-9 then 0, matching how the keys sit on the keyboard. There are more tools
# than number keys now, so any tool past the tenth is toolbar/wheel only. The
# paintbrush and washer sit last -- the washer already has its R / Backspace
# shortcut, and both are utilities rather than weapons.
HOTKEYS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
           pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0]


def build_tools() -> list[Tool]:
    tools = [Hammer(), Katana(), Gun(), Bow(), Rock(), Grenade(), RemoteBomb(),
             Gasoline(), Flamethrower(), Missile(), Paintbrush(), Washer()]
    # Hotkeys follow toolbar order, so the two can never drift apart as tools
    # are added or reordered.
    for tool, key in zip(tools, HOTKEYS):
        tool.key = key
    return tools
