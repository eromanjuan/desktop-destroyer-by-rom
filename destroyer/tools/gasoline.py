"""Gasoline: pour a slick, then set it off with fire or a blast.

This tool only lays the fuel down -- it can't light it. Sweep the flamethrower
over the slick, or set off a grenade or remote bomb next to it, and the whole
trail goes up and burns the screen for a good while before leaving a scorch.

The fuel itself lives in the shared FireSystem (ctx.fire), not on this tool, so
it survives you switching to the flamethrower to light it.
"""

from __future__ import annotations

import math

import pygame

from .base import Tool, ToolContext, iter_segment

POUR_STEP = 12.0          # spacing of pour blobs along a drag
COL_CAN = (196, 40, 34)   # jerry-can red


class Gasoline(Tool):
    id = "gasoline"
    label = "Gasoline"
    hint = "Pour it out  ·  then light it with flame or a blast"

    def __init__(self):
        self.pouring = False
        self.slosh = 0.0
        self.sound_timer = 0.0

    # -- input -------------------------------------------------------------
    def press(self, ctx: ToolContext, pos):
        self.pouring = True
        if ctx.fire is not None:
            ctx.fire.pour(pos, ctx.rng)
        ctx.audio.start_loop("pour")

    def hold(self, ctx: ToolContext, pos, prev, dt):
        if ctx.fire is not None:
            for point in iter_segment(prev, pos, POUR_STEP):
                ctx.fire.pour(point, ctx.rng)
        # A few amber droplets so the pour has some splash to it.
        if ctx.rng.random() < 0.4:
            ctx.particles.paint_spatter(pos, (150, 120, 40), count=ctx.rng.randint(1, 3))

    def update(self, ctx: ToolContext, dt, pos, held):
        self.slosh += dt
        if self.pouring and not held:
            self._stop(ctx)

    def release(self, ctx: ToolContext, pos):
        self._stop(ctx)

    def deactivate(self, ctx: ToolContext):
        self._stop(ctx)

    def _stop(self, ctx: ToolContext):
        if self.pouring:
            self.pouring = False
            ctx.audio.stop_loop("pour")

    # -- presentation ------------------------------------------------------
    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        body = pygame.Rect(cx - 9, cy - 6, 16, 15)
        pygame.draw.rect(surf, tint, body, border_radius=2)
        pygame.draw.rect(surf, tint, pygame.Rect(cx - 5, cy - 10, 8, 4), border_radius=1)
        pygame.draw.line(surf, tint, (cx + 7, cy - 4), (cx + 12, cy - 7), 2)  # spout

    def draw_cursor(self, surf, pos):
        x, y = pos
        # A tilted jerry can up and to the left, pouring toward the cursor.
        tilt = -0.5 - (0.35 if self.pouring else 0.0)
        cx, cy = x - 34, y - 30
        can = pygame.Surface((44, 46), pygame.SRCALPHA)
        pygame.draw.rect(can, COL_CAN, pygame.Rect(6, 12, 30, 30), border_radius=4)
        pygame.draw.rect(can, (150, 26, 22), pygame.Rect(6, 12, 30, 30), width=2, border_radius=4)
        pygame.draw.rect(can, (60, 60, 66), pygame.Rect(15, 4, 14, 9), border_radius=2)  # cap
        pygame.draw.line(can, (150, 26, 22), (11, 14), (31, 14), 2)                       # X-brace
        pygame.draw.line(can, (150, 26, 22), (11, 40), (31, 40), 2)
        rot = pygame.transform.rotate(can, math.degrees(-tilt))
        rect = rot.get_rect(center=(cx, cy))
        surf.blit(rot, rect)

        # Spout + a stream of gasoline arcing down to the cursor when pouring.
        spout = (cx + 16, cy + 2)
        pygame.draw.line(surf, (120, 90, 40), (cx + 8, cy - 6), spout, 4)
        if self.pouring:
            pts = []
            for i in range(9):
                t = i / 8.0
                sx = spout[0] + (x - spout[0]) * t
                sy = spout[1] + (y - spout[1]) * t + math.sin(t * 3.14) * 6
                pts.append((sx + math.sin(self.slosh * 30 + i) * 1.5, sy))
            if len(pts) > 1:
                pygame.draw.lines(surf, (208, 176, 84), False, pts, 3)
                pygame.draw.lines(surf, (150, 120, 40), False, pts, 1)
            pygame.draw.circle(surf, (208, 176, 84), (x, y), 4)

        pygame.draw.circle(surf, (255, 255, 255), pos, 2)
