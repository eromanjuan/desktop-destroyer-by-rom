"""RPG: fire a rocket-propelled grenade at where you click.

The rocket streaks in from the bottom of the screen on a smoke-and-fire trail
and detonates on arrival -- a bigger blast than a grenade, smaller than a nuke.
It lights gasoline, sets off planted bombs, and torches bugs, like any blast.
"""

from __future__ import annotations

import math

import pygame

from ..explosion import BlastFX, detonate
from .base import Tool, ToolContext

COOLDOWN = 0.5
FLIGHT = 0.45
SCALE = 1.6          # blast size relative to a grenade


class _Rocket:
    __slots__ = ("tx", "ty", "sx", "sy", "t")

    def __init__(self, target, sx, sy):
        self.tx, self.ty = target
        self.sx, self.sy = sx, sy
        self.t = 0.0

    def pos(self):
        e = self.t * self.t          # accelerates toward the target
        return (self.sx + (self.tx - self.sx) * e, self.sy + (self.ty - self.sy) * e)


class RPG(Tool):
    id = "rpg"
    label = "RPG"
    hint = "Click to fire a rocket"

    def __init__(self):
        self.rockets: list[_Rocket] = []
        self.fx = BlastFX()
        self.cooldown = 0.0

    # -- input -------------------------------------------------------------
    def press(self, ctx: ToolContext, pos):
        if self.cooldown <= 0.0:
            self._fire(ctx, pos)

    def hold(self, ctx: ToolContext, pos, prev, dt):
        if self.cooldown <= 0.0:
            self._fire(ctx, pos)

    def _fire(self, ctx: ToolContext, pos):
        self.cooldown = COOLDOWN
        w, h = ctx.size
        sx = ctx.rng.uniform(w * 0.35, w * 0.65)
        self.rockets.append(_Rocket(pos, sx, h + 40))
        ctx.audio.play("launch", volume=0.6)

    def update(self, ctx: ToolContext, dt, pos, held):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.fx.update(dt)
        for m in list(self.rockets):
            m.t += dt / FLIGHT
            px, py = m.pos()
            ctx.particles.smoke_cloud((px, py), count=1)
            if ctx.rng.random() < 0.7:
                ctx.particles.flame((px, py), drift=(0, 120), count=1)
            if m.t >= 1.0:
                self.rockets.remove(m)
                detonate(ctx, (m.tx, m.ty), self.fx, scale=SCALE)

    def deactivate(self, ctx: ToolContext):
        for m in self.rockets:
            detonate(ctx, (m.tx, m.ty), None, scale=SCALE)
        self.rockets.clear()
        self.fx.clear()

    # -- presentation ------------------------------------------------------
    def draw_overlay(self, surf, offset):
        ox, oy = offset
        for m in self.rockets:
            px, py = m.pos()
            px, py = px + ox, py + oy
            dx, dy = m.tx - m.sx, m.ty - m.sy
            length = math.hypot(dx, dy) or 1.0
            ux, uy = dx / length, dy / length
            tail = (px - ux * 20, py - uy * 20)
            pygame.draw.line(surf, (40, 40, 46), tail, (px, py), 7)
            pygame.draw.line(surf, (150, 90, 40), tail, (px, py), 4)
            # Warhead nose.
            pygame.draw.circle(surf, (210, 90, 40), (int(px), int(py)), 5)
            pygame.draw.circle(surf, (255, 210, 130), (int(px), int(py)), 2)
        self.fx.draw(surf, offset)

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        pygame.draw.line(surf, tint, (cx - 12, cy + 6), (cx + 8, cy - 6), 5)
        pygame.draw.polygon(surf, tint, [(cx + 8, cy - 10), (cx + 14, cy - 6), (cx + 6, cy - 2)])
        pygame.draw.line(surf, tint, (cx - 12, cy + 6), (cx - 15, cy + 10), 3)

    def draw_cursor(self, surf, pos):
        x, y = pos
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surf, (0, 0, 0), (x + dx * 6 + 1, y + dy * 6 + 1),
                             (x + dx * 14 + 1, y + dy * 14 + 1), 3)
            pygame.draw.line(surf, (255, 170, 70), (x + dx * 6, y + dy * 6),
                             (x + dx * 14, y + dy * 14), 2)
        pygame.draw.circle(surf, (255, 170, 70), (x, y), 3, 1)
