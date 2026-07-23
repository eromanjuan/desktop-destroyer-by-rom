"""Washer: scrub the original desktop back into view."""

from __future__ import annotations

import math

import pygame

from .. import decals
from .base import Tool, ToolContext, iter_segment

RADIUS = 52


class Washer(Tool):
    id = "wash"
    label = "Washer"
    hint = "Scrub to undo the damage"

    def __init__(self):
        self.scrubbing = False
        self.wobble = 0.0

    def update(self, ctx, dt, pos, held):
        self.wobble += dt
        if self.scrubbing and not held:
            self._stop(ctx)

    def press(self, ctx: ToolContext, pos):
        self.scrubbing = True
        ctx.audio.start_loop("wash")
        decals.soft_restore(ctx.world, ctx.pristine, pos, RADIUS)
        if ctx.fire is not None:
            ctx.fire.douse(pos, RADIUS, ctx)
        ctx.particles.water(pos, count=6)

    def hold(self, ctx: ToolContext, pos, prev, dt):
        r = ctx.rng
        moved = math.hypot(pos[0] - prev[0], pos[1] - prev[1])
        for point in iter_segment(prev, pos, RADIUS * 0.3):
            decals.soft_restore(ctx.world, ctx.pristine, point, RADIUS)
            if ctx.fire is not None:
                ctx.fire.douse(point, RADIUS, ctx)
        if moved > 3 and r.random() < 0.5:
            ctx.particles.water(pos, count=r.randint(2, 5))

    def release(self, ctx: ToolContext, pos):
        self._stop(ctx)

    def deactivate(self, ctx: ToolContext):
        self._stop(ctx)

    def _stop(self, ctx: ToolContext):
        if self.scrubbing:
            self.scrubbing = False
            ctx.audio.stop_loop("wash")

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        pygame.draw.rect(surf, tint, pygame.Rect(cx - 12, cy - 3, 24, 13), border_radius=4)
        pygame.draw.circle(surf, tint, (cx - 6, cy - 9), 4, 1)
        pygame.draw.circle(surf, tint, (cx + 3, cy - 12), 3, 1)
        pygame.draw.circle(surf, tint, (cx + 10, cy - 7), 2, 1)

    def draw_cursor(self, surf, pos):
        x, y = pos
        tilt = math.sin(self.wobble * 14.0) * 3.0 if self.scrubbing else 0.0
        body = pygame.Rect(0, 0, 40, 24)
        body.center = (x + tilt, y + 6)
        pygame.draw.rect(surf, (250, 216, 96), body, border_radius=7)
        pygame.draw.rect(surf, (196, 158, 52), body, width=2, border_radius=7)
        pygame.draw.rect(surf, (120, 206, 236),
                         pygame.Rect(body.x + 3, body.y + 2, body.w - 6, 7), border_radius=4)
        pygame.draw.circle(surf, (255, 255, 255, 160), (x, y), RADIUS, 1)
