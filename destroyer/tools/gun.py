"""Shotgun: a cone of bullet holes, muzzle flash, sparks, recoil."""

from __future__ import annotations

import math

import pygame

from .. import decals
from .base import Tool, ToolContext

COOLDOWN = 0.17
SPREAD = 42.0


class Gun(Tool):
    id = "gun"
    label = "Shotgun"
    hint = "Hold to unload"

    def __init__(self):
        self.cooldown = 0.0
        self.recoil = 0.0

    def update(self, ctx, dt, pos, held):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.recoil = max(0.0, self.recoil - dt * 5.0)

    def press(self, ctx: ToolContext, pos):
        self._fire(ctx, pos)

    def hold(self, ctx: ToolContext, pos, prev, dt):
        if self.cooldown <= 0.0:
            self._fire(ctx, pos)

    def _fire(self, ctx: ToolContext, pos):
        self.cooldown = COOLDOWN
        self.recoil = 1.0
        r = ctx.rng

        for _ in range(r.randint(5, 9)):
            ang = r.uniform(0, math.tau)
            dist = r.uniform(0, SPREAD) * r.uniform(0.4, 1.0)
            hit = (pos[0] + math.cos(ang) * dist, pos[1] + math.sin(ang) * dist)
            decals.bullet_hole(ctx.world, hit, r.randint(11, 18), r)
            ctx.particles.burst_sparks(hit, count=r.randint(3, 6), speed=(60, 300),
                                       color=(255, 220, 150), life=(0.1, 0.3))

        ctx.particles.muzzle_flash(pos, direction=(0, -1))
        ctx.particles.burst_debris(pos, count=r.randint(5, 9), speed=(90, 360))
        ctx.shake(0.5)
        ctx.audio.play("gunshot")

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        body = [(cx - 12, cy - 6), (cx + 11, cy - 6), (cx + 11, cy + 1),
                (cx - 2, cy + 1), (cx - 5, cy + 11), (cx - 12, cy + 11)]
        pygame.draw.polygon(surf, tint, body)
        pygame.draw.rect(surf, tint, pygame.Rect(cx + 2, cy + 1, 3, 5))

    def draw_cursor(self, surf, pos):
        x, y = pos
        kick = int(self.recoil * 5)
        col = (255, 255, 255)
        gap, arm = 6, 13
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surf, (0, 0, 0), (x + dx * gap + 1, y + dy * gap + 1),
                             (x + dx * arm + 1, y + dy * arm + 1), 3)
            pygame.draw.line(surf, col, (x + dx * gap, y + dy * gap),
                             (x + dx * arm, y + dy * arm), 2)
        pygame.draw.circle(surf, (255, 70, 40), (x, y + kick), 2)
