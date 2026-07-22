"""Remote bomb: mine the desktop, then set it all off at once.

  left click    place a charge (they sit there indefinitely, blinking)
  right click   detonate every charge you have placed

Chained blasts are staggered a few frames apart rather than fired on the same
frame. Simultaneous detonation just looks like one big flash and drops a pile of
identical work onto a single frame; a ripple reads as a chain reaction and
spreads the cost out.
"""

from __future__ import annotations

import math

import pygame

from ..explosion import BLAST, BlastFX, detonate
from ..toolbar import load_font
from .base import Tool, ToolContext

PLACE_COOLDOWN = 0.12
CHAIN_STAGGER = 0.07      # seconds between charges in a chain
MAX_CHARGES = 60          # generous, but stops a held click from melting things


class Charge:
    __slots__ = ("pos", "age")

    def __init__(self, pos):
        self.pos = pos
        self.age = 0.0


def draw_charge(surf, pos, blink_on: bool, scale: float = 1.0, armed: bool = False):
    """A taped brick of explosive with an antenna and a status light."""
    x, y = pos
    w, h = int(30 * scale), int(20 * scale)
    box = pygame.Rect(0, 0, w, h)
    box.center = (int(x), int(y))

    pygame.draw.rect(surf, (168, 132, 78), box, border_radius=3)
    pygame.draw.rect(surf, (96, 72, 40), box, width=2, border_radius=3)
    pygame.draw.rect(surf, (54, 58, 66), pygame.Rect(box.x, box.centery - int(3 * scale),
                                                     w, int(6 * scale)))
    # Antenna.
    pygame.draw.line(surf, (60, 62, 70), (box.centerx + w // 4, box.y),
                     (box.centerx + w // 4 + int(5 * scale), box.y - int(11 * scale)), 2)

    if blink_on:
        col = (255, 70, 44) if armed else (90, 230, 120)
        halo = pygame.Surface((22, 22), pygame.SRCALPHA)
        pygame.draw.circle(halo, (*col, 90), (11, 11), 8)
        surf.blit(halo, (box.centerx - w // 4 - 11, box.centery - 11))
        pygame.draw.circle(surf, col, (box.centerx - w // 4, box.centery), max(2, int(3 * scale)))


class RemoteBomb(Tool):
    id = "bomb"
    label = "Remote Bomb"
    hint = "Left-click to plant  ·  right-click to detonate all"

    def __init__(self):
        self.charges: list[Charge] = []
        self.pending: list[list] = []      # [pos, delay_remaining]
        self.fx = BlastFX()
        self.cooldown = 0.0
        self.blink = 0.0
        self.cursor = (0, 0)

    # -- input -------------------------------------------------------------
    def press(self, ctx: ToolContext, pos):
        self._plant(ctx, pos)

    def hold(self, ctx: ToolContext, pos, prev, dt):
        if self.cooldown <= 0.0:
            self._plant(ctx, pos)

    def alt_press(self, ctx: ToolContext, pos):
        self._detonate_all(ctx)

    def _plant(self, ctx: ToolContext, pos):
        if len(self.charges) >= MAX_CHARGES:
            return
        self.cooldown = PLACE_COOLDOWN
        self.charges.append(Charge(pos))
        ctx.audio.play("click", volume=0.8)

    def _detonate_all(self, ctx: ToolContext):
        if not self.charges:
            return
        # Ripple outward from the first one placed.
        for i, charge in enumerate(self.charges):
            self.pending.append([charge.pos, i * CHAIN_STAGGER])
        self.charges.clear()

    # -- simulation --------------------------------------------------------
    def update(self, ctx: ToolContext, dt, pos, held):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.blink += dt
        self.cursor = pos
        self.fx.update(dt)
        for charge in self.charges:
            charge.age += dt

        if self.pending:
            # Quieter per-blast the longer the chain, so the mixer doesn't clip.
            volume = max(0.35, 1.0 - 0.05 * len(self.pending))
            for item in list(self.pending):
                item[1] -= dt
                if item[1] <= 0.0:
                    self.pending.remove(item)
                    detonate(ctx, item[0], self.fx, volume=volume)

    def deactivate(self, ctx: ToolContext):
        # Planted charges survive a tool switch -- that's the point of them.
        # Anything already triggered still goes off, just immediately.
        for item in self.pending:
            detonate(ctx, item[0], None, volume=0.5)
        self.pending.clear()
        self.fx.clear()

    # -- presentation ------------------------------------------------------
    def draw_overlay(self, surf, offset):
        ox, oy = offset
        blink_on = math.sin(self.blink * math.tau * 1.6) > -0.3
        cx, cy = self.cursor
        for charge in self.charges:
            centre = (charge.pos[0] + ox, charge.pos[1] + oy)
            # Blast preview only for the charge you're standing near. Drawing a
            # full ring per charge turns a well-mined desktop into spaghetti.
            near = math.hypot(charge.pos[0] - cx, charge.pos[1] - cy) < BLAST * 1.15
            if near:
                steps = 40
                for i in range(0, steps, 2):
                    a0, a1 = (i / steps) * math.tau, ((i + 1) / steps) * math.tau
                    pygame.draw.line(
                        surf, (238, 108, 56),
                        (centre[0] + math.cos(a0) * BLAST, centre[1] + math.sin(a0) * BLAST),
                        (centre[0] + math.cos(a1) * BLAST, centre[1] + math.sin(a1) * BLAST), 2)
            draw_charge(surf, centre, blink_on)
        self.fx.draw(surf, offset)

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        pygame.draw.rect(surf, tint, pygame.Rect(cx - 11, cy - 2, 22, 13), border_radius=3)
        pygame.draw.line(surf, tint, (cx + 5, cy - 2), (cx + 9, cy - 11), 2)
        pygame.draw.circle(surf, tint, (cx - 5, cy + 4), 2)

    def draw_cursor(self, surf, pos):
        x, y = pos
        armed = bool(self.charges)
        draw_charge(surf, (x - 28, y + 14), True, scale=0.9, armed=armed)

        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surf, (0, 0, 0), (x + dx * 5 + 1, y + dy * 5 + 1),
                             (x + dx * 12 + 1, y + dy * 12 + 1), 3)
            pygame.draw.line(surf, (255, 255, 255), (x + dx * 5, y + dy * 5),
                             (x + dx * 12, y + dy * 12), 2)

        if armed:
            text = _label_font().render(f"{len(self.charges)} planted  ·  right-click",
                                        True, (255, 236, 220))
            box = text.get_rect()
            box.inflate_ip(14, 10)
            box.midtop = (x, y + 30)
            panel = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.rect(panel, (28, 18, 16, 210), panel.get_rect(), border_radius=7)
            pygame.draw.rect(panel, (255, 120, 60, 120), panel.get_rect(),
                             width=1, border_radius=7)
            panel.blit(text, ((box.w - text.get_width()) // 2,
                              (box.h - text.get_height()) // 2))
            surf.blit(panel, box.topleft)


_label: pygame.font.Font | None = None


def _label_font() -> pygame.font.Font:
    """Built on first use -- pygame.font isn't ready at import time."""
    global _label
    if _label is None:
        _label = load_font(13, bold=True)
    return _label
