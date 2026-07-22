"""Katana: drag out a stroke, release to cut.

Aiming the cut before it lands is what makes this different from the hammer.
While the button is held you're winding up a stroke and the blade shows you
exactly where it will fall; the damage only happens on release.

Very short drags are treated as a flick and get a stroke of their own, so a
quick click still cuts rather than doing nothing.
"""

from __future__ import annotations

import math

import pygame

from .. import decals
from .base import Tool, ToolContext

MIN_CUT = 46.0            # a click this short becomes a flick cut instead
TRAIL_TIME = 0.22


class Katana(Tool):
    id = "katana"
    label = "Katana"
    hint = "Drag out a stroke, release to cut"

    def __init__(self):
        self.origin: tuple[int, int] | None = None
        self.current = (0, 0)
        self.trails: list[list] = []       # [p0, p1, t]
        self.glint = 0.0

    # -- input -------------------------------------------------------------
    def press(self, ctx: ToolContext, pos):
        self.origin = pos
        self.current = pos

    def hold(self, ctx: ToolContext, pos, prev, dt):
        self.current = pos

    def release(self, ctx: ToolContext, pos):
        if self.origin is None:
            return
        start = self.origin
        self.origin = None

        dx, dy = pos[0] - start[0], pos[1] - start[1]
        if math.hypot(dx, dy) < MIN_CUT:
            # Flick: cut through the click point on a pleasing diagonal.
            ang = math.radians(ctx.rng.uniform(-38, -22))
            half = ctx.rng.uniform(70, 120)
            start = (pos[0] - math.cos(ang) * half, pos[1] - math.sin(ang) * half)
            pos = (pos[0] + math.cos(ang) * half, pos[1] + math.sin(ang) * half)
        self._cut(ctx, start, pos)

    def update(self, ctx: ToolContext, dt, pos, held):
        self.glint += dt
        for trail in list(self.trails):
            trail[2] += dt / TRAIL_TIME
            if trail[2] >= 1.0:
                self.trails.remove(trail)

    def deactivate(self, ctx: ToolContext):
        self.origin = None
        self.trails.clear()

    # -- cutting -----------------------------------------------------------
    def _cut(self, ctx: ToolContext, p0, p1):
        r = ctx.rng
        length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        decals.slash(ctx.world, p0, p1, r, width=r.uniform(7.0, 11.0))

        # Sparks struck all along the cut.
        for _ in range(int(min(46, length / 9))):
            t = r.random()
            at = (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)
            ctx.particles.burst_sparks(at, count=1, speed=(60, 320),
                                       color=(255, 236, 190), life=(0.12, 0.4))
        ctx.particles.burst_glass((p0[0] + (p1[0] - p0[0]) * 0.5,
                                   p0[1] + (p1[1] - p0[1]) * 0.5),
                                  count=int(min(18, length / 22)))

        self.trails.append([p0, p1, 0.0])
        ctx.shake(min(0.7, 0.18 + length / 1400.0))
        ctx.audio.play("slash")

    # -- presentation ------------------------------------------------------
    def draw_overlay(self, surf, offset):
        ox, oy = offset
        for p0, p1, t in self.trails:
            fade = (1.0 - t) ** 1.5
            a = (p0[0] + ox, p0[1] + oy)
            b = (p1[0] + ox, p1[1] + oy)
            pygame.draw.line(surf, (int(255 * fade), int(240 * fade), int(210 * fade)),
                             a, b, max(1, int(9 * fade)))
            pygame.draw.line(surf, (int(255 * fade), int(255 * fade), int(255 * fade)),
                             a, b, max(1, int(3 * fade)))

        # The wind-up: show the stroke that is about to land.
        if self.origin is not None:
            a = (self.origin[0] + ox, self.origin[1] + oy)
            b = (self.current[0] + ox, self.current[1] + oy)
            pygame.draw.line(surf, (10, 10, 12), a, b, 3)
            pygame.draw.line(surf, (255, 250, 240), a, b, 1)
            pygame.draw.circle(surf, (255, 250, 240), a, 4, 1)

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        pygame.draw.line(surf, tint, (cx - 11, cy + 10), (cx + 9, cy - 10), 3)
        pygame.draw.line(surf, tint, (cx - 13, cy + 12), (cx - 7, cy + 6), 4)

    def draw_cursor(self, surf, pos):
        x, y = pos
        # Blade points up-right from the cursor, edge catching a moving glint.
        tipx, tipy = x + 54, y - 54
        pygame.draw.line(surf, (24, 24, 28), (x - 16, y + 16), (tipx, tipy), 8)
        pygame.draw.line(surf, (198, 206, 220), (x - 12, y + 12), (tipx, tipy), 5)
        pygame.draw.line(surf, (250, 252, 255), (x - 11, y + 11), (tipx - 1, tipy + 1), 2)

        # Guard and grip.
        pygame.draw.circle(surf, (46, 40, 34), (x - 16, y + 16), 6)
        pygame.draw.circle(surf, (206, 176, 96), (x - 16, y + 16), 6, 2)
        pygame.draw.line(surf, (38, 34, 30), (x - 16, y + 16), (x - 34, y + 34), 7)
        pygame.draw.line(surf, (92, 82, 74), (x - 16, y + 16), (x - 34, y + 34), 3)

        # A highlight sliding along the edge.
        g = (math.sin(self.glint * 2.4) * 0.5 + 0.5)
        gx = x - 11 + (tipx - x + 11) * g
        gy = y + 11 + (tipy - y - 11) * g
        pygame.draw.circle(surf, (255, 255, 255), (int(gx), int(gy)), 3)
