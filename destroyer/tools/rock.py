"""Rock: the cheap, satisfying one. Lob a stone, crack the screen, no fuse.

Same arc-in-and-land shape as the grenade but with the payload on arrival, so
you can hammer away at a screen with it. Each rock is a different lumpy
silhouette, generated once when thrown.
"""

from __future__ import annotations

import math

import pygame

from .. import decals
from .base import Tool, ToolContext

FLIGHT_TIME = 0.30
COOLDOWN = 0.22
ARC_HEIGHT = 150.0


class Stone:
    __slots__ = ("target", "start", "t", "spin", "shape", "size")

    def __init__(self, target, start, rng):
        self.target = target
        self.start = start
        self.t = 0.0
        self.spin = rng.uniform(0, math.tau)
        self.size = rng.uniform(11, 17)
        # Lumpy outline, fixed per rock so it tumbles as one solid object.
        self.shape = [
            (math.cos(i * math.tau / 8) * rng.uniform(0.62, 1.0),
             math.sin(i * math.tau / 8) * rng.uniform(0.62, 1.0))
            for i in range(8)
        ]

    @property
    def pos(self):
        t = min(1.0, self.t)
        x = self.start[0] + (self.target[0] - self.start[0]) * t
        y = self.start[1] + (self.target[1] - self.start[1]) * t
        return (x, y - math.sin(math.pi * t) * ARC_HEIGHT)


def draw_stone(surf, pos, shape, size, spin, tint=(104, 100, 96)):
    c, s = math.cos(spin), math.sin(spin)
    pts = [(pos[0] + (px * c - py * s) * size, pos[1] + (px * s + py * c) * size)
           for px, py in shape]
    pygame.draw.polygon(surf, (44, 42, 40), [(x + 2, y + 2) for x, y in pts])
    pygame.draw.polygon(surf, tint, pts)
    pygame.draw.polygon(surf, (58, 56, 54), pts, 2)
    # A lit facet, so it reads as a solid lump rather than a flat blob.
    pygame.draw.polygon(surf, (146, 142, 136), pts[:3] + [pos])


class Rock(Tool):
    id = "rock"
    label = "Rock"
    hint = "Click to throw  ·  hold to keep throwing"

    def __init__(self):
        self.stones: list[Stone] = []
        self.cooldown = 0.0

    # -- input -------------------------------------------------------------
    def press(self, ctx: ToolContext, pos):
        self._throw(ctx, pos)

    def hold(self, ctx: ToolContext, pos, prev, dt):
        if self.cooldown <= 0.0:
            self._throw(ctx, pos)

    def update(self, ctx: ToolContext, dt, pos, held):
        self.cooldown = max(0.0, self.cooldown - dt)
        for stone in list(self.stones):
            stone.t += dt / FLIGHT_TIME
            stone.spin += dt * 9.0
            if stone.t >= 1.0:
                self.stones.remove(stone)
                self._impact(ctx, stone)

    def deactivate(self, ctx: ToolContext):
        for stone in self.stones:
            self._impact(ctx, stone)
        self.stones.clear()

    # -- behaviour ---------------------------------------------------------
    def _throw(self, ctx: ToolContext, pos):
        self.cooldown = COOLDOWN
        r = ctx.rng
        start = (pos[0] - r.uniform(200, 380), pos[1] + r.uniform(160, 300))
        self.stones.append(Stone(pos, start, r))
        ctx.audio.play("toss", volume=0.7)

    def _impact(self, ctx: ToolContext, stone: Stone):
        r = ctx.rng
        pos = stone.target
        heft = stone.size / 17.0

        decals.impact_crack(ctx.world, pos, int(34 + 30 * heft), r)
        for _ in range(r.randint(2, 4)):       # chipped-out flakes
            ang = r.uniform(0, math.tau)
            d = r.uniform(8, 34)
            decals.bullet_hole(ctx.world, (pos[0] + math.cos(ang) * d,
                                           pos[1] + math.sin(ang) * d), r.randint(4, 8), r)

        ctx.particles.burst_debris(pos, count=r.randint(10, 18), speed=(120, 520))
        ctx.particles.burst_glass(pos, count=r.randint(6, 12))
        ctx.particles.smoke_cloud(pos, count=3)     # puff of dust
        ctx.shake(0.3 + 0.35 * heft)
        ctx.audio.play("rock")

    # -- presentation ------------------------------------------------------
    def draw_overlay(self, surf, offset):
        ox, oy = offset
        for stone in self.stones:
            p = (stone.pos[0] + ox, stone.pos[1] + oy)
            draw_stone(surf, p, stone.shape, stone.size, stone.spin)

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        pygame.draw.polygon(surf, tint, [(cx - 11, cy + 2), (cx - 5, cy - 9), (cx + 6, cy - 10),
                                         (cx + 12, cy - 1), (cx + 7, cy + 10), (cx - 6, cy + 10)])

    def draw_cursor(self, surf, pos):
        x, y = pos
        draw_stone(surf, (x - 26, y + 16),
                   [(math.cos(i * math.tau / 8) * (0.7 + 0.3 * ((i * 5) % 3) / 2.0),
                     math.sin(i * math.tau / 8) * (0.7 + 0.3 * ((i * 7) % 3) / 2.0))
                    for i in range(8)], 14, 0.4)

        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surf, (0, 0, 0), (x + dx * 5 + 1, y + dy * 5 + 1),
                             (x + dx * 12 + 1, y + dy * 12 + 1), 3)
            pygame.draw.line(surf, (255, 255, 255), (x + dx * 5, y + dy * 5),
                             (x + dx * 12, y + dy * 12), 2)
