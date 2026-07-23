"""Flamethrower: continuous flame while held, leaving char behind."""

from __future__ import annotations

import math

import pygame

from .. import decals
from .base import Tool, ToolContext, iter_segment

SCORCH_INTERVAL = 0.024
FLAME_RATE = 150.0          # particles per second while held


class Flamethrower(Tool):
    id = "flame"
    label = "Flamethrower"
    hint = "Hold and drag to burn"

    def __init__(self):
        self.burning = False
        self.scorch_timer = 0.0
        self.emit_debt = 0.0
        self.flicker = 0.0

    def update(self, ctx, dt, pos, held):
        self.flicker += dt
        if self.burning and not held:
            self._stop(ctx)

    def press(self, ctx: ToolContext, pos):
        self.burning = True
        self.scorch_timer = 0.0
        ctx.audio.play("ignite")
        ctx.audio.start_loop("flame")

    def hold(self, ctx: ToolContext, pos, prev, dt):
        r = ctx.rng
        drift = ((pos[0] - prev[0]) / max(dt, 1e-4), (pos[1] - prev[1]) / max(dt, 1e-4))

        # Emit a frame-rate independent number of flame particles, carrying the
        # fractional remainder so low frame times don't quietly drop emissions.
        self.emit_debt += FLAME_RATE * dt
        count = int(self.emit_debt)
        self.emit_debt -= count
        if count > 0:
            ctx.particles.flame(pos, drift=drift, count=count)

        # Sweeping the flame over gasoline sets it alight.
        if ctx.fire is not None:
            ctx.fire.ignite(pos, 26.0, ctx)

        # Char builds up along the whole dragged path, not just the endpoint.
        self.scorch_timer += dt
        if self.scorch_timer >= SCORCH_INTERVAL:
            self.scorch_timer = 0.0
            for point in iter_segment(prev, pos, 9.0):
                decals.scorch(ctx.world, point, r.randint(26, 44), r,
                              strength=r.randint(48, 72))

    def release(self, ctx: ToolContext, pos):
        self._stop(ctx)

    def deactivate(self, ctx: ToolContext):
        self._stop(ctx)

    def _stop(self, ctx: ToolContext):
        if self.burning:
            self.burning = False
            ctx.audio.stop_loop("flame")

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        flame = [(cx, cy - 13), (cx + 8, cy - 2), (cx + 6, cy + 8),
                 (cx, cy + 12), (cx - 6, cy + 8), (cx - 8, cy - 2)]
        pygame.draw.polygon(surf, tint, flame)
        pygame.draw.polygon(surf, (255, 150, 60), [(cx, cy - 4), (cx + 4, cy + 3),
                                                   (cx, cy + 8), (cx - 4, cy + 3)])

    def draw_cursor(self, surf, pos):
        x, y = pos
        nozzle = [(x - 12, y + 10), (x - 4, y + 2), (x + 4, y + 6), (x - 4, y + 16)]
        pygame.draw.polygon(surf, (0, 0, 0), [(px + 1, py + 1) for px, py in nozzle])
        pygame.draw.polygon(surf, (188, 194, 204), nozzle)
        pygame.draw.line(surf, (90, 96, 106), (x - 12, y + 10), (x - 20, y + 18), 4)

        pulse = 3 + 2 * math.sin(self.flicker * 22.0)
        pygame.draw.circle(surf, (255, 170, 60), (x, y), int(pulse), 1)
