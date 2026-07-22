"""Bow: draw it back, loose an arrow, leave it stuck in the screen.

The only tool with a charge mechanic. Holding the button pulls the string; the
longer the draw, the faster the arrow flies and the harder it bites. A full draw
shatters the surface around the impact instead of just puncturing it.

Arrows exist in three stages:
  1. nocked   -- part of the cursor, moving with the mouse
  2. in flight -- transient, drawn via draw_overlay(), not yet damage
  3. stuck    -- burned into `world` permanently by decals.stuck_arrow()
"""

from __future__ import annotations

import math

import pygame

from .. import decals
from .base import Tool, ToolContext

DRAW_TIME = 0.62          # seconds of holding for a full-power shot
MIN_CHARGE = 0.22         # a twitch-click still fires, just weakly
FLIGHT_DIST = 320.0       # how far off-target an arrow starts
BOW_OFFSET = 74           # cursor-space distance from crosshair to the bow


class Arrow:
    """An arrow between release and impact."""

    __slots__ = ("target", "dx", "dy", "angle", "charge", "t", "duration")

    def __init__(self, target, angle: float, charge: float):
        self.target = target
        self.angle = angle
        rad = math.radians(angle)
        self.dx, self.dy = math.cos(rad), math.sin(rad)
        self.charge = charge
        self.t = 0.0
        self.duration = 0.20 - 0.09 * charge      # a full draw arrives sooner

    @property
    def tip(self):
        """Head position: starts out along `angle`, arrives at the target."""
        back = (1.0 - self.t) * FLIGHT_DIST
        return (self.target[0] + self.dx * back, self.target[1] + self.dy * back)


class Bow(Tool):
    id = "bow"
    label = "Bow"
    hint = "Hold to draw, release to loose"

    def __init__(self):
        self.charge = 0.0
        self.drawing_bow = False
        self.arrows: list[Arrow] = []

    # -- input -------------------------------------------------------------
    def press(self, ctx: ToolContext, pos):
        self.drawing_bow = True
        self.charge = 0.0

    def hold(self, ctx: ToolContext, pos, prev, dt):
        self.charge = min(1.0, self.charge + dt / DRAW_TIME)

    def release(self, ctx: ToolContext, pos):
        if self.drawing_bow:
            self._loose(ctx, pos)

    def update(self, ctx: ToolContext, dt, pos, held):
        for arrow in list(self.arrows):
            arrow.t += dt / arrow.duration
            if arrow.t >= 1.0:
                self.arrows.remove(arrow)
                self._impact(ctx, arrow)

    def deactivate(self, ctx: ToolContext):
        # Switching tools mid-flight shouldn't strand arrows in mid-air.
        for arrow in self.arrows:
            self._impact(ctx, arrow)
        self.arrows.clear()
        self.drawing_bow = False
        self.charge = 0.0

    # -- firing ------------------------------------------------------------
    def _loose(self, ctx: ToolContext, pos):
        charge = max(MIN_CHARGE, self.charge)
        self.drawing_bow = False
        self.charge = 0.0
        # Flies in from the side the bow is on, so the shot reads as coming
        # off the string rather than out of nowhere.
        angle = 180.0 + ctx.rng.uniform(-11.0, 11.0)
        self.arrows.append(Arrow(pos, angle, charge))
        ctx.audio.play("bow", volume=0.55 + 0.45 * charge)

    def _impact(self, ctx: ToolContext, arrow: Arrow):
        r = ctx.rng
        pos = arrow.target
        charge = arrow.charge

        decals.bullet_hole(ctx.world, pos, int(8 + 9 * charge), r)
        if charge > 0.75:
            decals.impact_crack(ctx.world, pos, int(34 + 26 * charge), r)
        decals.stuck_arrow(ctx.world, pos, arrow.angle, 46 + 26 * charge, r)

        ctx.particles.burst_debris(pos, count=int(5 + 12 * charge),
                                   speed=(80, 260 + 320 * charge))
        ctx.particles.burst_glass(pos, count=int(3 + 8 * charge))
        ctx.shake(0.22 + 0.68 * charge)
        ctx.audio.play("thunk", volume=0.5 + 0.5 * charge)

    # -- presentation ------------------------------------------------------
    def draw_overlay(self, surf, offset):
        ox, oy = offset
        for arrow in self.arrows:
            tip = (arrow.tip[0] + ox, arrow.tip[1] + oy)
            # Streak behind the head so a fast arrow doesn't strobe.
            trail = (tip[0] + arrow.dx * 46, tip[1] + arrow.dy * 46)
            pygame.draw.line(surf, (30, 28, 26), tip, trail, 4)
            pygame.draw.line(surf, (242, 240, 232), tip, trail, 2)
            decals.draw_arrow(surf, tip, arrow.angle, 52 + 22 * arrow.charge,
                              scale=0.82 + 0.18 * arrow.t)

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        pygame.draw.arc(surf, tint, pygame.Rect(cx - 12, cy - 14, 20, 28), -1.25, 1.25, 3)
        pygame.draw.line(surf, tint, (cx - 3, cy - 13), (cx - 3, cy + 13), 1)
        pygame.draw.line(surf, tint, (cx - 6, cy), (cx + 12, cy), 2)
        pygame.draw.polygon(surf, tint, [(cx + 13, cy), (cx + 6, cy - 4), (cx + 6, cy + 4)])

    def draw_cursor(self, surf, pos):
        x, y = pos
        bx = x - BOW_OFFSET
        pull = self.charge * 20.0

        limb = pygame.Rect(bx - 26, y - 40, 52, 80)
        pygame.draw.arc(surf, (44, 28, 16), limb, -1.2, 1.2, 7)
        pygame.draw.arc(surf, (132, 90, 50), limb, -1.2, 1.2, 4)

        # String from limb tips back to the nocking point. At rest the nock sits
        # on the chord between the tips, so the string is taut rather than slack.
        tip_x = bx + 26 * math.cos(1.2)
        tip_dy = 40 * math.sin(1.2)
        nock = (tip_x - pull, y)
        # Dark under, light over: a plain white string vanishes on a pale desktop.
        for end in ((tip_x, y - tip_dy), (tip_x, y + tip_dy)):
            pygame.draw.line(surf, (26, 24, 28), end, nock, 3)
            pygame.draw.line(surf, (240, 240, 246), end, nock, 1)

        # The nocked arrow, aimed at the crosshair.
        if self.drawing_bow:
            decals.draw_arrow(surf, (x - 8, y), 180.0, (x - 8) - nock[0], scale=0.9)

        # Draw-strength meter under the bow.
        meter = pygame.Rect(bx - 22, y + 52, 44, 5)
        pygame.draw.rect(surf, (0, 0, 0, 120), meter, border_radius=3)
        if self.charge > 0.01:
            fill = meter.copy()
            fill.width = max(2, int(meter.width * self.charge))
            hot = self.charge >= 1.0
            pygame.draw.rect(surf, (255, 226, 90) if hot else (240, 128, 52),
                             fill, border_radius=3)

        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surf, (0, 0, 0), (x + dx * 5 + 1, y + dy * 5 + 1),
                             (x + dx * 11 + 1, y + dy * 11 + 1), 3)
            pygame.draw.line(surf, (255, 255, 255), (x + dx * 5, y + dy * 5),
                             (x + dx * 11, y + dy * 11), 2)
