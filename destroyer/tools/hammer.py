"""Hammer: crater the desktop, shake the screen, spray glass."""

from __future__ import annotations

import pygame

from .. import decals
from .base import Tool, ToolContext, blit_pivoted

COOLDOWN = 0.20
SWING_TIME = 0.16

_sprite: pygame.Surface | None = None


def _hammer_sprite() -> pygame.Surface:
    """Small side-on hammer, grip at the bottom-left."""
    global _sprite
    if _sprite is None:
        s = pygame.Surface((54, 54), pygame.SRCALPHA)
        pygame.draw.line(s, (74, 48, 30), (10, 48), (34, 16), 7)
        pygame.draw.line(s, (110, 74, 46), (10, 48), (34, 16), 3)
        head = [(24, 8), (48, 2), (52, 14), (30, 22)]
        pygame.draw.polygon(s, (58, 62, 70), head)
        pygame.draw.polygon(s, (150, 158, 172), [(26, 9), (46, 4), (47, 8), (28, 13)])
        pygame.draw.polygon(s, (30, 33, 38), head, 2)
        _sprite = s
    return _sprite


class Hammer(Tool):
    id = "hammer"
    label = "Hammer"
    hint = "Click to smash"

    def __init__(self):
        self.cooldown = 0.0
        self.swing = 0.0

    def update(self, ctx, dt, pos, held):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.swing = max(0.0, self.swing - dt)

    def press(self, ctx: ToolContext, pos):
        self._smash(ctx, pos)

    def hold(self, ctx: ToolContext, pos, prev, dt):
        if self.cooldown <= 0.0:
            self._smash(ctx, pos)

    def _smash(self, ctx: ToolContext, pos):
        self.cooldown = COOLDOWN
        self.swing = SWING_TIME
        r = ctx.rng

        radius = r.randint(46, 78)
        decals.impact_crack(ctx.world, pos, radius, r)
        ctx.particles.burst_debris(pos, count=r.randint(10, 18))
        ctx.particles.burst_glass(pos, count=r.randint(8, 14))
        ctx.particles.burst_sparks(pos, count=6, speed=(60, 240),
                                   color=(255, 190, 110), life=(0.12, 0.32))
        if ctx.bugs is not None:
            ctx.bugs.hit(ctx, pos, radius * 0.6, "smash")
        if ctx.fire is not None:            # knock any stuck shuriken/kunai loose
            ctx.fire.dislodge(pos, radius)
        ctx.shake(0.85)
        ctx.audio.play("hammer")

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        pygame.draw.line(surf, tint, (cx - 9, cy + 10), (cx + 4, cy - 4), 4)
        pygame.draw.polygon(surf, tint, [(cx - 1, cy - 12), (cx + 12, cy - 8),
                                         (cx + 9, cy + 1), (cx - 4, cy - 3)])

    def draw_cursor(self, surf, pos):
        # Wind up, then snap down on impact.
        t = self.swing / SWING_TIME if SWING_TIME else 0.0
        angle = -58.0 * (t ** 0.55)
        blit_pivoted(surf, _hammer_sprite(), (10, 48), (pos[0] - 4, pos[1] + 6), angle)
        pygame.draw.circle(surf, (255, 255, 255, 120), pos, 2)
