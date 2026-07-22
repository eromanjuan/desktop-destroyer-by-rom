"""Tool interface + shared drawing helpers.

Adding a tool means: subclass `Tool`, implement the hooks you care about, and
append it to the list in `tools/__init__.py`. Nothing else in the app needs to
change -- the toolbar, keybindings and input routing are all driven by that list.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Iterator

import pygame


@dataclass
class ToolContext:
    """Everything a tool is allowed to touch."""

    world: pygame.Surface        # mutable screenshot -- draw damage here
    pristine: pygame.Surface     # untouched capture -- read-only, for restoring
    particles: "object"          # ParticleSystem
    audio: "object"              # Audio
    rng: random.Random
    shake: Callable[[float], None]
    size: tuple[int, int]


class Tool:
    id: str = ""
    label: str = ""
    hint: str = ""
    key: int | None = None

    # -- input hooks (all optional) ----------------------------------------
    def press(self, ctx: ToolContext, pos: tuple[int, int]) -> None:
        """Mouse button went down."""

    def hold(self, ctx: ToolContext, pos: tuple[int, int],
             prev: tuple[int, int], dt: float) -> None:
        """Called every frame while the button is held."""

    def release(self, ctx: ToolContext, pos: tuple[int, int]) -> None:
        """Mouse button came up."""

    def alt_press(self, ctx: ToolContext, pos: tuple[int, int]) -> None:
        """Right mouse button went down. Optional secondary action."""

    def update(self, ctx: ToolContext, dt: float,
               pos: tuple[int, int], held: bool) -> None:
        """Called every frame regardless of input -- animation bookkeeping."""

    def deactivate(self, ctx: ToolContext) -> None:
        """Tool was switched away from, or the app is closing. Kill loops here."""

    # -- presentation ------------------------------------------------------
    def draw_overlay(self, surf: pygame.Surface, offset: tuple[float, float]) -> None:
        """Draw world-space visuals that aren't damage and aren't particles.

        Called every frame after the particles, with the same shake offset, so
        anything drawn here sits in the world rather than on the UI. Projectiles
        in flight live here -- they aren't permanent yet, so they mustn't touch
        `world`, and they aren't simple enough to be particles.
        """

    def draw_icon(self, surf: pygame.Surface, rect: pygame.Rect, tint) -> None:
        raise NotImplementedError

    def draw_cursor(self, surf: pygame.Surface, pos: tuple[int, int]) -> None:
        pygame.draw.circle(surf, (255, 255, 255), pos, 6, 1)


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------
def iter_segment(prev, pos, step: float) -> Iterator[tuple[float, float]]:
    """Walk evenly spaced points from `prev` to `pos`.

    Continuous tools need this: at 120 fps a fast drag still jumps tens of
    pixels between frames, and stamping only at the endpoint leaves gaps.
    """
    dx, dy = pos[0] - prev[0], pos[1] - prev[1]
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        yield (float(pos[0]), float(pos[1]))
        return
    count = max(1, int(dist / max(0.5, step)))
    for i in range(1, count + 1):
        t = i / count
        yield (prev[0] + dx * t, prev[1] + dy * t)


def blit_pivoted(surf: pygame.Surface, image: pygame.Surface,
                 pivot: tuple[float, float], pos: tuple[float, float],
                 angle: float) -> None:
    """Blit `image` rotated by `angle` degrees about `pivot` (image-space)."""
    rotated = pygame.transform.rotate(image, angle)
    offset = pygame.math.Vector2(
        pivot[0] - image.get_width() / 2.0,
        pivot[1] - image.get_height() / 2.0,
    ).rotate(-angle)
    rect = rotated.get_rect(center=(pos[0] - offset.x, pos[1] - offset.y))
    surf.blit(rotated, rect)


def shadowed_polygon(surf, points, color, shadow=(0, 0, 0, 110), offset=(1, 2)) -> None:
    pygame.draw.polygon(surf, shadow, [(x + offset[0], y + offset[1]) for x, y in points])
    pygame.draw.polygon(surf, color, points)


def hsv_color(hue: float, sat: float = 0.85, val: float = 1.0) -> tuple[int, int, int]:
    """Cheap HSV -> RGB. `hue` is in turns (0..1), wrapped."""
    h = (hue % 1.0) * 6.0
    i = int(h)
    f = h - i
    p = val * (1.0 - sat)
    q = val * (1.0 - sat * f)
    t = val * (1.0 - sat * (1.0 - f))
    r, g, b = [(val, t, p), (q, val, p), (p, val, t),
               (p, q, val), (t, p, val), (val, p, q)][i % 6]
    return int(r * 255), int(g * 255), int(b * 255)
