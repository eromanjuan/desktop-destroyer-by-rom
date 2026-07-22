"""Grenade: lob it, watch the fuse, take cover.

Unlike most tools the payload is delayed, so a grenade moves through states of
its own:

  FLIGHT   arcing toward the target, tumbling
  FUSE     sat on the desktop, indicator blinking faster as time runs out
  (boom)   handed off to explosion.detonate()

You can have several in the air at once -- they each keep their own fuse.
"""

from __future__ import annotations

import math

import pygame

from ..explosion import BLAST, BlastFX, detonate
from .base import Tool, ToolContext

FLIGHT_TIME = 0.42
FUSE_TIME = 1.15
COOLDOWN = 0.40
ARC_HEIGHT = 190.0

FLIGHT, FUSE = 0, 1


class Bomb:
    """One thrown grenade, from leaving the hand to going off."""

    __slots__ = ("target", "start", "state", "timer", "spin")

    def __init__(self, target, start):
        self.target = target
        self.start = start
        self.state = FLIGHT
        self.timer = 0.0
        self.spin = 0.0

    @property
    def pos(self):
        if self.state != FLIGHT:
            return self.target
        t = min(1.0, self.timer / FLIGHT_TIME)
        x = self.start[0] + (self.target[0] - self.start[0]) * t
        y = self.start[1] + (self.target[1] - self.start[1]) * t
        return (x, y - math.sin(math.pi * t) * ARC_HEIGHT)   # lob, not a straight line

    @property
    def fuse_left(self) -> float:
        return 1.0 if self.state == FLIGHT else max(0.0, 1.0 - self.timer / FUSE_TIME)


def draw_grenade_body(surf, pos, spin=0.0, fuse_left=1.0,
                      in_flight=False, scale=1.0, led=(255, 60, 40)):
    """Grenade body, spoon, and an indicator that panics as the fuse runs out.

    Shared with the remote bomb's cursor so the two read as the same hardware.
    """
    x, y = pos
    body = pygame.Surface((int(40 * scale), int(46 * scale)), pygame.SRCALPHA)
    w, h = body.get_size()

    pygame.draw.ellipse(body, (52, 66, 44), pygame.Rect(4, 8, w - 8, h - 14))
    pygame.draw.ellipse(body, (28, 36, 24), pygame.Rect(4, 8, w - 8, h - 14), 2)
    for i in range(3):                      # segmented "pineapple" body
        yy = 14 + i * int(9 * scale)
        pygame.draw.line(body, (32, 42, 28), (6, yy), (w - 6, yy), 1)
    pygame.draw.line(body, (34, 44, 30), (w // 2, 10), (w // 2, h - 8), 1)
    pygame.draw.rect(body, (96, 100, 92), pygame.Rect(w // 2 - 5, 2, 10, 8), border_radius=2)
    pygame.draw.line(body, (150, 154, 146), (w // 2 + 5, 4), (w // 2 + 9, 16), 3)

    if in_flight:
        body = pygame.transform.rotate(body, math.degrees(spin))
    surf.blit(body, body.get_rect(center=(x, y)))

    rate = 4.0 + (1.0 - fuse_left) * 22.0
    if math.sin(pygame.time.get_ticks() * 0.001 * rate * math.tau) > 0.0:
        glow = int(120 + 135 * (1.0 - fuse_left))
        lx, ly = int(x + 8 * scale), int(y - 14 * scale)
        halo = pygame.Surface((26, 26), pygame.SRCALPHA)
        pygame.draw.circle(halo, (*led, glow // 2), (13, 13), 9)
        surf.blit(halo, (lx - 13, ly - 13))
        pygame.draw.circle(surf, led, (lx, ly), max(2, int(3 * scale)))


class Grenade(Tool):
    id = "grenade"
    label = "Grenade"
    hint = "Click to lob  ·  1.2s fuse"

    def __init__(self):
        self.grenades: list[Bomb] = []
        self.fx = BlastFX()
        self.cooldown = 0.0

    # -- input -------------------------------------------------------------
    def press(self, ctx: ToolContext, pos):
        self._throw(ctx, pos)

    def hold(self, ctx: ToolContext, pos, prev, dt):
        if self.cooldown <= 0.0:
            self._throw(ctx, pos)

    def update(self, ctx: ToolContext, dt, pos, held):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.fx.update(dt)

        for g in list(self.grenades):
            g.timer += dt
            if g.state == FLIGHT:
                g.spin += dt * 14.0
                if g.timer >= FLIGHT_TIME:
                    g.state = FUSE
                    g.timer = 0.0
            elif g.timer >= FUSE_TIME:
                self.grenades.remove(g)
                detonate(ctx, g.target, self.fx)

    def deactivate(self, ctx: ToolContext):
        # A thrown grenade always goes off -- don't let a tool switch defuse it.
        for g in self.grenades:
            detonate(ctx, g.target, None)
        self.grenades.clear()
        self.fx.clear()

    def _throw(self, ctx: ToolContext, pos):
        self.cooldown = COOLDOWN
        r = ctx.rng
        start = (pos[0] - r.uniform(240, 420), pos[1] + r.uniform(180, 340))
        self.grenades.append(Bomb(pos, start))
        ctx.audio.play("toss")

    # -- presentation ------------------------------------------------------
    def draw_overlay(self, surf, offset):
        ox, oy = offset
        for g in self.grenades:
            p = (g.pos[0] + ox, g.pos[1] + oy)
            draw_grenade_body(surf, p, g.spin, g.fuse_left, in_flight=g.state == FLIGHT)
        self.fx.draw(surf, offset)

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        pygame.draw.ellipse(surf, tint, pygame.Rect(cx - 8, cy - 5, 16, 18))
        pygame.draw.rect(surf, tint, pygame.Rect(cx - 3, cy - 11, 6, 6), border_radius=2)
        pygame.draw.line(surf, tint, (cx + 3, cy - 10), (cx + 9, cy - 2), 2)

    def draw_cursor(self, surf, pos):
        x, y = pos
        # Dashed blast radius, so the throw is aimed rather than hoped.
        steps = 44
        for i in range(0, steps, 2):
            a0, a1 = (i / steps) * math.tau, ((i + 1) / steps) * math.tau
            pygame.draw.line(
                surf, (255, 120, 60),
                (x + math.cos(a0) * BLAST, y + math.sin(a0) * BLAST),
                (x + math.cos(a1) * BLAST, y + math.sin(a1) * BLAST), 2)

        draw_grenade_body(surf, (x - 26, y + 12), scale=0.85)

        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surf, (0, 0, 0), (x + dx * 6 + 1, y + dy * 6 + 1),
                             (x + dx * 13 + 1, y + dy * 13 + 1), 3)
            pygame.draw.line(surf, (255, 255, 255), (x + dx * 6, y + dy * 6),
                             (x + dx * 13, y + dy * 13), 2)
