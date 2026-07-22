"""Paintbrush: rainbow strokes that shift hue as you drag."""

from __future__ import annotations

import math

import pygame

from .. import decals
from .base import Tool, ToolContext, hsv_color, iter_segment

RADIUS = 15
HUE_PER_PIXEL = 0.0012


class Paintbrush(Tool):
    id = "brush"
    label = "Paintbrush"
    hint = "Drag to paint  ·  hue shifts as you go"

    def __init__(self):
        self.hue = 0.0
        self.sound_timer = 0.0

    @property
    def color(self):
        return hsv_color(self.hue)

    def update(self, ctx, dt, pos, held):
        self.sound_timer = max(0.0, self.sound_timer - dt)
        if not held:
            self.hue += dt * 0.06        # idle shimmer so the cursor stays alive

    def press(self, ctx: ToolContext, pos):
        decals.paint_stamp(ctx.world, pos, RADIUS, self.color)
        ctx.audio.play("paint")

    def hold(self, ctx: ToolContext, pos, prev, dt):
        r = ctx.rng
        dist = math.hypot(pos[0] - prev[0], pos[1] - prev[1])
        for point in iter_segment(prev, pos, RADIUS * 0.34):
            self.hue += HUE_PER_PIXEL * RADIUS * 0.34
            decals.paint_stamp(ctx.world, point, RADIUS, self.color)

        if dist > 6 and r.random() < 0.25:
            ctx.particles.paint_spatter(pos, self.color, count=r.randint(2, 5))
        if self.sound_timer <= 0.0 and dist > 2:
            self.sound_timer = 0.22
            ctx.audio.play("paint", volume=0.7)

    def draw_icon(self, surf, rect, tint):
        cx, cy = rect.center
        pygame.draw.line(surf, tint, (cx + 9, cy - 12), (cx - 2, cy + 1), 4)
        pygame.draw.polygon(surf, tint, [(cx - 5, cy - 2), (cx + 2, cy + 5),
                                         (cx - 4, cy + 12), (cx - 11, cy + 5)])
        pygame.draw.circle(surf, hsv_color(0.06), (cx - 4, cy + 5), 3)

    def draw_cursor(self, surf, pos):
        x, y = pos
        pygame.draw.line(surf, (58, 42, 30), (x + 14, y - 18), (x + 2, y - 4), 6)
        pygame.draw.line(surf, (172, 178, 190), (x + 4, y - 6), (x - 1, y - 1), 7)
        bristles = [(x - 6, y - 6), (x + 2, y - 2), (x - 2, y + 10), (x - 12, y + 3)]
        pygame.draw.polygon(surf, self.color, bristles)
        pygame.draw.polygon(surf, (0, 0, 0, 90), bristles, 1)
        pygame.draw.circle(surf, self.color, (x, y), RADIUS, 1)
