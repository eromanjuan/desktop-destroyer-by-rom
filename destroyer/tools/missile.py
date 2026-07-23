"""Missile strike: lock targets, then rain nukes on them.

  left click    drop a targeting lock (up to 10 at once)
  right click   launch -- one nuclear missile streaks in on every locked mark

Each warhead flattens a huge chunk of the screen: roughly a fifth of it goes to
a charred crater, and the blast sets off any gasoline or planted bombs caught in
it. Launches are staggered a hair apart so ten strikes land as a rolling
bombardment rather than one white frame.
"""

from __future__ import annotations

import math

import pygame

from .. import decals
from ..explosion import BlastFX
from .base import Tool, ToolContext

MAX_LOCKS = 10
AREA_FRAC = 0.18          # crater area as a fraction of the whole screen
LAUNCH_STAGGER = 0.12     # seconds between successive missiles in a salvo
FALL_TIME = 0.75          # seconds from the top of the screen to impact
FLASH_TIME = 0.5


class _Missile:
    """One warhead falling from the top of the screen toward a locked mark."""

    __slots__ = ("tx", "ty", "sx", "delay", "t")

    def __init__(self, target, sx, delay):
        self.tx, self.ty = target
        self.sx = sx                 # where it enters at the top edge
        self.delay = delay           # stagger before this one launches
        self.t = 0.0                 # 0 launched .. 1 impact

    def pos(self):
        e = self.t * self.t          # accelerates as it drops
        return (self.sx + (self.tx - self.sx) * e, -60 + (self.ty + 60) * e)


class Missile(Tool):
    id = "missile"
    label = "Nuke Strike"
    hint = "Click to lock targets  ·  right-click to launch"

    def __init__(self):
        self.locks: list[tuple[int, int]] = []
        self.missiles: list[_Missile] = []
        self.fx = BlastFX()
        self.flash = 0.0
        self.blink = 0.0
        self.nuke_r = 200

    # -- input -------------------------------------------------------------
    def press(self, ctx: ToolContext, pos):
        if len(self.locks) < MAX_LOCKS:
            self.locks.append(pos)
            ctx.audio.play("lock")

    def alt_press(self, ctx: ToolContext, pos):
        self._launch(ctx)

    def _launch(self, ctx: ToolContext):
        if not self.locks:
            return
        w, h = ctx.size
        self.nuke_r = min(int(math.sqrt(AREA_FRAC * w * h / math.pi)), int(0.46 * min(w, h)))
        for i, target in enumerate(self.locks):
            sx = target[0] + ctx.rng.uniform(-120, 120)
            self.missiles.append(_Missile(target, sx, i * LAUNCH_STAGGER))
        self.locks = []
        ctx.audio.play("launch")

    # -- simulation --------------------------------------------------------
    def update(self, ctx: ToolContext, dt, pos, held):
        self.blink += dt
        self.flash = max(0.0, self.flash - dt)
        self.fx.update(dt)
        for m in list(self.missiles):
            if m.delay > 0.0:
                m.delay -= dt
                continue
            m.t += dt / FALL_TIME
            px, py = m.pos()
            ctx.particles.smoke_cloud((px, py), count=1)      # contrail
            if ctx.rng.random() < 0.6:
                ctx.particles.flame((px, py), drift=(0, -140), count=1)
            if m.t >= 1.0:
                self.missiles.remove(m)
                self._impact(ctx, (m.tx, m.ty))

    def _impact(self, ctx: ToolContext, pos):
        r = ctx.rng
        R = self.nuke_r
        decals.nuke_crater(ctx.world, pos, R, r)

        ctx.particles.add_glow(pos, size=R * 1.3, end_size=R * 0.3, life=0.35,
                               color=(255, 248, 224), end_color=(255, 130, 30))
        ctx.particles.fireball(pos, count=140)
        ctx.particles.smoke_cloud(pos, count=70)
        ctx.particles.burst_debris(pos, count=90, speed=(300, 1500))
        ctx.particles.burst_sparks(pos, count=60, speed=(260, 1200),
                                   color=(255, 210, 140), life=(0.4, 1.2))
        # Mushroom stem: a column of smoke rising out of the centre.
        for _ in range(24):
            ctx.particles.smoke_cloud((pos[0] + r.uniform(-20, 20), pos[1] - r.uniform(0, R)),
                                      count=1)

        self.fx.add(pos, intensity=1.0)
        self.flash = FLASH_TIME
        ctx.shake(1.0)
        if ctx.fire is not None:                    # set off gasoline and bombs
            ctx.fire.ignite(pos, R * 0.85, ctx)
        ctx.audio.play("nuke", volume=max(0.5, 1.0 - 0.05 * len(self.missiles)))

    def deactivate(self, ctx: ToolContext):
        # A launched salvo still lands even if you switch away mid-flight.
        for m in self.missiles:
            self._impact(ctx, (m.tx, m.ty))
        self.missiles.clear()
        self.fx.clear()
        self.flash = 0.0

    # -- presentation ------------------------------------------------------
    def draw_overlay(self, surf, offset):
        ox, oy = offset

        pulse = 0.6 + 0.4 * math.sin(self.blink * 8.0)
        for i, (lx, ly) in enumerate(self.locks):
            x, y = int(lx + ox), int(ly + oy)
            col = (255, int(60 + 60 * pulse), 40)
            pygame.draw.circle(surf, col, (x, y), 18, 2)
            pygame.draw.circle(surf, col, (x, y), int(9 * pulse) + 4, 1)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                pygame.draw.line(surf, col, (x + dx * 12, y + dy * 12),
                                 (x + dx * 22, y + dy * 22), 2)
            surf.blit(_lab_font().render(str(i + 1), True, (255, 235, 220)), (x + 20, y - 26))

        for m in self.missiles:
            if m.delay > 0.0:
                continue
            px, py = m.pos()
            px, py = px + ox, py + oy
            dx, dy = (m.tx - m.sx), (m.ty + 60)
            length = math.hypot(dx, dy) or 1.0
            ux, uy = dx / length, dy / length
            tail = (px - ux * 22, py - uy * 22)
            pygame.draw.line(surf, (40, 40, 46), tail, (px, py), 6)
            pygame.draw.line(surf, (210, 214, 222), tail, (px, py), 3)
            pygame.draw.circle(surf, (255, 220, 150), (int(px), int(py)), 4)

        self.fx.draw(surf, offset, blast=self.nuke_r)

        if self.flash > 0.0:
            k = self.flash / FLASH_TIME
            lvl = int(150 * k * k)
            surf.fill((lvl, int(lvl * 0.92), int(lvl * 0.8)), special_flags=pygame.BLEND_RGB_ADD)

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        pygame.draw.circle(surf, tint, (cx, cy), 11, 2)
        pygame.draw.circle(surf, tint, (cx, cy), 2)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surf, tint, (cx + dx * 7, cy + dy * 7),
                             (cx + dx * 14, cy + dy * 14), 2)

    def draw_cursor(self, surf, pos):
        x, y = pos
        col = (255, 70, 44)
        pygame.draw.circle(surf, (0, 0, 0), (x, y), 15, 4)
        pygame.draw.circle(surf, col, (x, y), 15, 2)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surf, (0, 0, 0), (x + dx * 9 + 1, y + dy * 9 + 1),
                             (x + dx * 20 + 1, y + dy * 20 + 1), 4)
            pygame.draw.line(surf, col, (x + dx * 9, y + dy * 9),
                             (x + dx * 20, y + dy * 20), 2)
        pygame.draw.circle(surf, col, (x, y), 2)

        if self.locks:
            text = _lab_font().render(f"{len(self.locks)} locked  ·  right-click to launch",
                                      True, (255, 235, 220))
            box = text.get_rect(); box.inflate_ip(14, 10)
            box.midtop = (x, y + 28)
            panel = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.rect(panel, (30, 14, 12, 214), panel.get_rect(), border_radius=7)
            pygame.draw.rect(panel, (255, 90, 60, 130), panel.get_rect(), width=1, border_radius=7)
            panel.blit(text, ((box.w - text.get_width()) // 2, (box.h - text.get_height()) // 2))
            surf.blit(panel, box.topleft)


_lab: pygame.font.Font | None = None


def _lab_font() -> pygame.font.Font:
    global _lab
    if _lab is None:
        from ..toolbar import load_font
        _lab = load_font(13, bold=True)
    return _lab
