"""Shuriken: a ninja throwing star, switchable to a kunai.

  left click    hurl one at the cursor -- hold to keep throwing
  right click   swap between the four-point star and the kunai dagger

The star slices (an X of cuts, and it cleaves bugs in two); the kunai stabs (a
punched hole, and it drops bugs with a spurt of blood). Both spin in from the
edge of the screen and strike where you clicked.
"""

from __future__ import annotations

import math

import pygame

from .. import decals
from .base import Tool, ToolContext

COOLDOWN = 0.16
FLIGHT = 0.20
THROW_DIST = 420.0


class _Blade:
    __slots__ = ("tx", "ty", "sx", "sy", "t", "spin", "kind", "heading")

    def __init__(self, target, sx, sy, kind):
        self.tx, self.ty = target
        self.sx, self.sy = sx, sy
        self.t = 0.0
        self.spin = 0.0
        self.kind = kind         # "star" | "kunai"
        # Direction of travel -- the kunai flies point-first along this.
        self.heading = math.degrees(math.atan2(target[1] - sy, target[0] - sx))

    def pos(self):
        e = self.t
        return (self.sx + (self.tx - self.sx) * e, self.sy + (self.ty - self.sy) * e)


class Shuriken(Tool):
    id = "shuriken"
    label = "Shuriken"
    hint = "Click to throw  ·  right-click swaps star / kunai"

    def __init__(self):
        self.kind = "star"
        self.blades: list[_Blade] = []
        self.cooldown = 0.0
        self.spin = 0.0

    # -- input -------------------------------------------------------------
    def press(self, ctx: ToolContext, pos):
        self._throw(ctx, pos)

    def hold(self, ctx: ToolContext, pos, prev, dt):
        if self.cooldown <= 0.0:
            self._throw(ctx, pos)

    def alt_press(self, ctx: ToolContext, pos):
        self.kind = "kunai" if self.kind == "star" else "star"
        ctx.audio.play("click", volume=0.6)

    def _throw(self, ctx: ToolContext, pos):
        self.cooldown = COOLDOWN
        r = ctx.rng
        ang = r.uniform(0, math.tau)
        sx = pos[0] + math.cos(ang) * THROW_DIST
        sy = pos[1] + math.sin(ang) * THROW_DIST
        self.blades.append(_Blade(pos, sx, sy, self.kind))
        ctx.audio.play("slash", volume=0.4)

    def update(self, ctx: ToolContext, dt, pos, held):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.spin += dt * 26.0
        for b in list(self.blades):
            b.t += dt / FLIGHT
            b.spin += dt * 40.0
            if b.t >= 1.0:
                self.blades.remove(b)
                self._impact(ctx, b)

    def _impact(self, ctx: ToolContext, b: _Blade):
        r = ctx.rng
        pos = (b.tx, b.ty)
        if b.kind == "star":
            a = r.uniform(0, math.pi)
            for da in (0.0, math.pi / 2):
                ux, uy = math.cos(a + da), math.sin(a + da)
                decals.slash(ctx.world, (pos[0] - ux * 16, pos[1] - uy * 16),
                             (pos[0] + ux * 16, pos[1] + uy * 16), r, width=4.0)
            # The star embeds as a knock-loose-able pin; the cuts stay for good.
            if ctx.fire is not None:
                ctx.fire.add_pin(pos, math.degrees(a), "star")
            else:
                decals.stuck_shuriken(ctx.world, pos, math.degrees(a), r)
            ctx.particles.burst_sparks(pos, count=6, speed=(80, 300),
                                       color=(220, 230, 245), life=(0.1, 0.3))
            if ctx.bugs is not None:
                ctx.bugs.hit(ctx, pos, 22, "slice")
        else:  # kunai -- stabs in point-first and stays stuck
            decals.bullet_hole(ctx.world, pos, r.randint(4, 6), r)   # the puncture stays
            if ctx.fire is not None:
                ctx.fire.add_pin(pos, b.heading, "kunai")
            else:
                decals.stuck_kunai(ctx.world, pos, b.heading, r)
            ctx.particles.burst_debris(pos, count=r.randint(4, 8), speed=(90, 340))
            if ctx.bugs is not None:
                ctx.bugs.hit(ctx, pos, 16, "shot")
        ctx.shake(0.18)
        ctx.audio.play("thunk", volume=0.4)

    # -- presentation ------------------------------------------------------
    def draw_overlay(self, surf, offset):
        ox, oy = offset
        for b in self.blades:
            px, py = b.pos()
            if b.kind == "star":
                decals.draw_shuriken(surf, px + ox, py + oy, b.spin, 1.0)
            else:
                # Kunai flies point-first: nose leads, so put the tip a little
                # ahead of its current position along the heading.
                a = math.radians(b.heading)
                tip = (px + ox + math.cos(a) * 14, py + oy + math.sin(a) * 14)
                decals.draw_kunai(surf, tip, b.heading, 1.15)

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        pts = []
        for i in range(8):
            a = i * math.pi / 4
            rad = 11 if i % 2 == 0 else 4
            pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
        pygame.draw.polygon(surf, tint, pts, 2)
        pygame.draw.circle(surf, tint, (cx, cy), 2)

    def draw_cursor(self, surf, pos):
        x, y = pos
        if self.kind == "star":
            decals.draw_shuriken(surf, x - 26, y - 22, self.spin, 0.9)   # spins in hand
        else:
            decals.draw_kunai(surf, (x - 18, y - 30), 120.0, 0.95)       # held ready
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surf, (0, 0, 0), (x + dx * 5 + 1, y + dy * 5 + 1),
                             (x + dx * 11 + 1, y + dy * 11 + 1), 3)
            pygame.draw.line(surf, (240, 244, 250), (x + dx * 5, y + dy * 5),
                             (x + dx * 11, y + dy * 11), 2)
        lab = _tag_font().render(self.kind.upper(), True, (235, 238, 245))
        surf.blit(lab, (x + 12, y + 12))


_tag: pygame.font.Font | None = None


def _tag_font() -> pygame.font.Font:
    global _tag
    if _tag is None:
        from ..toolbar import load_font
        _tag = load_font(11, bold=True)
    return _tag
