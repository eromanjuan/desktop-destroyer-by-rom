"""Remote bomb: mine the desktop, then set it all off at once.

  left click    place a charge (they sit there indefinitely, blinking)
  right click   detonate every charge you have placed

The charges themselves live in the shared FireSystem, not on this tool. That is
what lets a charge go off on its own the instant fire reaches it -- a spreading
gasoline fire, a burning arrow, or another blast -- with no remote needed, even
while you are holding a completely different tool. This class is just the
controller: it plants charges and pulls the remote trigger.
"""

from __future__ import annotations

import math

import pygame

from ..explosion import BLAST
from ..toolbar import load_font
from .base import Tool, ToolContext

PLACE_COOLDOWN = 0.12
MAX_CHARGES = 60          # generous, but stops a held click from melting things


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
        self.cooldown = 0.0
        self._count = 0        # cached from the fire system, for the cursor label

    # -- input -------------------------------------------------------------
    def press(self, ctx: ToolContext, pos):
        self._plant(ctx, pos)

    def hold(self, ctx: ToolContext, pos, prev, dt):
        if self.cooldown <= 0.0:
            self._plant(ctx, pos)

    def alt_press(self, ctx: ToolContext, pos):
        if ctx.fire is not None and ctx.fire.detonate_all(ctx):
            ctx.audio.play("click", volume=0.6)

    def _plant(self, ctx: ToolContext, pos):
        if ctx.fire is None or ctx.fire.charge_count >= MAX_CHARGES:
            return
        self.cooldown = PLACE_COOLDOWN
        ctx.fire.add_charge(pos)
        ctx.audio.play("click", volume=0.8)

    def update(self, ctx: ToolContext, dt, pos, held):
        self.cooldown = max(0.0, self.cooldown - dt)
        self._count = ctx.fire.charge_count if ctx.fire is not None else 0

    # -- presentation ------------------------------------------------------
    def draw_overlay(self, surf, offset):
        # The charges and their blasts are drawn by the fire system every frame
        # (so they stay visible under any tool). Here we only preview the blast
        # radius at the cursor, where the next charge will land.
        x, y = pygame.mouse.get_pos()
        steps = 40
        for i in range(0, steps, 2):
            a0, a1 = (i / steps) * math.tau, ((i + 1) / steps) * math.tau
            pygame.draw.line(
                surf, (238, 108, 56),
                (x + math.cos(a0) * BLAST, y + math.sin(a0) * BLAST),
                (x + math.cos(a1) * BLAST, y + math.sin(a1) * BLAST), 1)

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        pygame.draw.rect(surf, tint, pygame.Rect(cx - 11, cy - 2, 22, 13), border_radius=3)
        pygame.draw.line(surf, tint, (cx + 5, cy - 2), (cx + 9, cy - 11), 2)
        pygame.draw.circle(surf, tint, (cx - 5, cy + 4), 2)

    def draw_cursor(self, surf, pos):
        x, y = pos
        armed = self._count > 0
        draw_charge(surf, (x - 28, y + 14), True, scale=0.9, armed=armed)

        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surf, (0, 0, 0), (x + dx * 5 + 1, y + dy * 5 + 1),
                             (x + dx * 12 + 1, y + dy * 12 + 1), 3)
            pygame.draw.line(surf, (255, 255, 255), (x + dx * 5, y + dy * 5),
                             (x + dx * 12, y + dy * 12), 2)

        if armed:
            text = _label_font().render(f"{self._count} planted  ·  right-click",
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
