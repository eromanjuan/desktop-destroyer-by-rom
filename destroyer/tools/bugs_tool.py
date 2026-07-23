"""Bugs: drop ants and flies onto the screen for the fun of squashing them.

  left click    place a bug at the cursor -- hold and drag to scatter a trail
  right click   switch between placing ants and flies

The bugs wander on their own once placed, and die to whatever weapon hits them:
sliced by the katana, splatted by the hammer, shot, or burned. Nothing spawns on
its own -- the screen only has the bugs you put there.
"""

from __future__ import annotations

import pygame

from ..bugs import ANT, FLY, _draw_ant, _draw_fly
from .base import Tool, ToolContext

PLACE_COOLDOWN = 0.06


class Bugs(Tool):
    id = "bug"
    label = "Bugs"
    hint = "Click to place  ·  right-click swaps ant / fly"

    def __init__(self):
        self.kind = ANT
        self.cooldown = 0.0
        self.wiggle = 0.0

    # -- input -------------------------------------------------------------
    def press(self, ctx: ToolContext, pos):
        self._place(ctx, pos)

    def hold(self, ctx: ToolContext, pos, prev, dt):
        if self.cooldown <= 0.0:
            self._place(ctx, pos)

    def alt_press(self, ctx: ToolContext, pos):
        self.kind = FLY if self.kind == ANT else ANT
        ctx.audio.play("click", volume=0.5)

    def _place(self, ctx: ToolContext, pos):
        self.cooldown = PLACE_COOLDOWN
        if ctx.bugs is not None:
            ctx.bugs.spawn_at(pos, self.kind)

    def update(self, ctx: ToolContext, dt, pos, held):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.wiggle += dt * 9.0

    # -- presentation ------------------------------------------------------
    def draw_icon(self, surf, rect, tint):
        # A simple ant silhouette: three body dots, legs, antennae.
        cx, cy = rect.center
        for dx in (-6, 0, 6):
            pygame.draw.circle(surf, tint, (cx + dx, cy), 4 if dx else 3)
        for dx in (-6, -2, 2, 6):
            pygame.draw.line(surf, tint, (cx + dx * 0.5, cy), (cx + dx, cy + 7), 1)
            pygame.draw.line(surf, tint, (cx + dx * 0.5, cy), (cx + dx, cy - 7), 1)
        pygame.draw.line(surf, tint, (cx + 6, cy), (cx + 11, cy - 4), 1)
        pygame.draw.line(surf, tint, (cx + 6, cy), (cx + 11, cy + 4), 1)

    def draw_cursor(self, surf, pos):
        x, y = pos
        # A little preview of what will be placed, walking beside the cursor.
        if self.kind == ANT:
            _draw_ant(surf, x - 24, y - 20, 0.0, self.wiggle, 1.6)
        else:
            _draw_fly(surf, x - 24, y - 20, 0.0, self.wiggle, 1.6)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surf, (0, 0, 0), (x + dx * 5 + 1, y + dy * 5 + 1),
                             (x + dx * 10 + 1, y + dy * 10 + 1), 3)
            pygame.draw.line(surf, (120, 210, 120), (x + dx * 5, y + dy * 5),
                             (x + dx * 10, y + dy * 10), 2)
        lab = _tag_font().render("ANT" if self.kind == ANT else "FLY", True, (225, 240, 225))
        surf.blit(lab, (x + 12, y + 12))


_tag: pygame.font.Font | None = None


def _tag_font() -> pygame.font.Font:
    global _tag
    if _tag is None:
        from ..toolbar import load_font
        _tag = load_font(11, bold=True)
    return _tag
