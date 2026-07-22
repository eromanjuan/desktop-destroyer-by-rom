"""Particle system.

Four render kinds cover everything the tools need:

  GLOW   additive radial sprite  -> sparks, flame, muzzle flash
  SMOKE  soft alpha-blended blob -> smoke, steam
  CHUNK  rotating solid quad     -> debris, glass shards
  DROP   small round droplet     -> water, paint spatter

Glow sprites are cached by (radius, quantised colour) so a few hundred flame
particles a frame cost a few hundred cheap blits and no per-pixel Python.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pygame

from .config import MAX_PARTICLES

GLOW, SMOKE, CHUNK, DROP = 0, 1, 2, 3

_glow_cache: dict[tuple[int, int, int, int], pygame.Surface] = {}
_falloff_cache: dict[int, np.ndarray] = {}
_smoke_cache: dict[int, pygame.Surface] = {}


def _falloff(radius: int) -> np.ndarray:
    """Normalised radial intensity ramp, 1.0 at the centre -> 0.0 at the rim."""
    f = _falloff_cache.get(radius)
    if f is None:
        size = radius * 2
        yy, xx = np.mgrid[0:size, 0:size]
        dist = np.sqrt((xx - radius + 0.5) ** 2 + (yy - radius + 0.5) ** 2) / radius
        f = np.clip(1.0 - dist, 0.0, 1.0).astype(np.float32) ** 1.9
        _falloff_cache[radius] = f
    return f


def glow_sprite(radius: int, color: tuple[float, float, float]) -> pygame.Surface:
    """Additive glow disc. Colour is quantised to keep the cache small."""
    radius = max(1, min(48, int(radius)))
    key = (radius, int(color[0]) >> 4, int(color[1]) >> 4, int(color[2]) >> 4)
    surf = _glow_cache.get(key)
    if surf is None:
        if len(_glow_cache) > 900:
            _glow_cache.clear()
        f = _falloff(radius)
        rgb = np.empty((radius * 2, radius * 2, 3), np.uint8)
        for i in range(3):
            rgb[:, :, i] = np.clip(f * min(255, (key[1 + i] << 4) + 8), 0, 255).astype(np.uint8)
        surf = pygame.image.frombuffer(
            np.ascontiguousarray(rgb), (radius * 2, radius * 2), "RGB"
        ).convert()
        _glow_cache[key] = surf
    return surf


def smoke_sprite(radius: int) -> pygame.Surface:
    radius = max(2, min(64, int(radius)))
    surf = _smoke_cache.get(radius)
    if surf is None:
        if len(_smoke_cache) > 80:
            _smoke_cache.clear()
        size = radius * 2
        f = _falloff(radius)
        rgba = np.zeros((size, size, 4), np.uint8)
        rgba[:, :, :3] = 255
        rgba[:, :, 3] = np.clip(f * 255, 0, 255).astype(np.uint8)
        surf = pygame.image.frombuffer(
            np.ascontiguousarray(rgba), (size, size), "RGBA"
        ).convert_alpha()
        _smoke_cache[radius] = surf
    return surf


_tinted_smoke_cache: dict[tuple[int, int], pygame.Surface] = {}


def tinted_smoke(radius: int, shade: int) -> pygame.Surface:
    """Grey-tinted smoke puff, cached so we never copy a surface per frame."""
    radius = max(2, min(64, int(radius)))
    key = (radius, max(0, min(255, int(shade))) >> 4)
    surf = _tinted_smoke_cache.get(key)
    if surf is None:
        if len(_tinted_smoke_cache) > 400:
            _tinted_smoke_cache.clear()
        value = (key[1] << 4) + 8
        surf = smoke_sprite(radius).copy()
        surf.fill((value, value, value, 255), special_flags=pygame.BLEND_RGBA_MULT)
        _tinted_smoke_cache[key] = surf
    return surf


class Particle:
    __slots__ = (
        "x", "y", "vx", "vy", "life", "max_life", "size", "end_size",
        "color", "end_color", "kind", "grav", "drag", "rot", "vrot", "alpha",
    )

    def __init__(self, x, y, vx, vy, life, size, color, kind,
                 grav=0.0, drag=0.0, end_size=None, end_color=None,
                 rot=0.0, vrot=0.0, alpha=1.0):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = self.max_life = life
        self.size = size
        self.end_size = size * 0.2 if end_size is None else end_size
        self.color = color
        self.end_color = color if end_color is None else end_color
        self.kind = kind
        self.grav = grav
        self.drag = drag
        self.rot = rot
        self.vrot = vrot
        self.alpha = alpha


def _lerp(a, b, t):
    return a + (b - a) * t


class ParticleSystem:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.items: list[Particle] = []

    def __len__(self) -> int:
        return len(self.items)

    def add(self, p: Particle) -> None:
        if len(self.items) < MAX_PARTICLES:
            self.items.append(p)

    def clear(self) -> None:
        self.items.clear()

    # -- emitters ----------------------------------------------------------
    def burst_sparks(self, pos, count=14, speed=(90, 460), color=(255, 210, 120), life=(0.2, 0.6)):
        r = self.rng
        for _ in range(count):
            ang = r.uniform(0, math.tau)
            spd = r.uniform(*speed)
            self.add(Particle(
                pos[0], pos[1], math.cos(ang) * spd, math.sin(ang) * spd,
                r.uniform(*life), r.uniform(2.0, 5.0), color, GLOW,
                grav=520.0, drag=1.6, end_color=(90, 30, 10),
            ))

    def burst_debris(self, pos, count=12, speed=(120, 520), color=(58, 58, 66)):
        r = self.rng
        for _ in range(count):
            ang = r.uniform(0, math.tau)
            spd = r.uniform(*speed)
            shade = r.uniform(0.6, 1.35)
            self.add(Particle(
                pos[0], pos[1], math.cos(ang) * spd, math.sin(ang) * spd,
                r.uniform(0.5, 1.2), r.uniform(2.5, 6.5),
                tuple(min(255, int(c * shade)) for c in color), CHUNK,
                grav=1250.0, drag=0.4, rot=r.uniform(0, math.tau), vrot=r.uniform(-14, 14),
            ))

    def burst_glass(self, pos, count=10):
        r = self.rng
        for _ in range(count):
            ang = r.uniform(0, math.tau)
            spd = r.uniform(160, 620)
            tint = r.choice([(206, 226, 244), (236, 244, 252), (170, 200, 226)])
            self.add(Particle(
                pos[0], pos[1], math.cos(ang) * spd, math.sin(ang) * spd,
                r.uniform(0.45, 1.0), r.uniform(2.0, 5.0), tint, CHUNK,
                grav=1350.0, drag=0.3, rot=r.uniform(0, math.tau), vrot=r.uniform(-20, 20),
            ))

    def muzzle_flash(self, pos, direction=(0, -1)):
        r = self.rng
        self.add(Particle(pos[0], pos[1], 0, 0, 0.075, 42.0, (255, 236, 190), GLOW,
                          end_size=8.0, end_color=(255, 130, 40)))
        for _ in range(7):
            ang = math.atan2(direction[1], direction[0]) + r.uniform(-0.7, 0.7)
            spd = r.uniform(200, 640)
            self.add(Particle(
                pos[0], pos[1], math.cos(ang) * spd, math.sin(ang) * spd,
                r.uniform(0.08, 0.24), r.uniform(3, 7), (255, 220, 150), GLOW,
                drag=3.2, end_color=(200, 70, 20),
            ))

    def flame(self, pos, drift=(0.0, 0.0), count=3):
        """Fire is drawn additively, so start orange -- overlapping particles
        blow out to white-hot on their own where the flame is densest."""
        r = self.rng
        for _ in range(count):
            ang = r.uniform(0, math.tau)
            spd = r.uniform(10, 90)
            self.add(Particle(
                pos[0] + r.uniform(-5, 5), pos[1] + r.uniform(-5, 5),
                math.cos(ang) * spd + drift[0] * 0.35,
                math.sin(ang) * spd + drift[1] * 0.35 - r.uniform(40, 130),
                r.uniform(0.28, 0.62), r.uniform(9, 20),
                (255, 146, 42), GLOW, drag=1.5, end_size=r.uniform(2, 7),
                end_color=(146, 18, 4),
            ))
        # Sparse smoke: any more and the grey swamps the fire entirely.
        if r.random() < 0.12:
            self.add(Particle(
                pos[0] + r.uniform(-8, 8), pos[1] + r.uniform(-8, 8),
                r.uniform(-24, 24), -r.uniform(30, 90),
                r.uniform(0.7, 1.4), r.uniform(10, 18), (44, 38, 36), SMOKE,
                drag=0.7, end_size=r.uniform(30, 52), alpha=0.30,
            ))

    def add_glow(self, pos, size, end_size, life, color, end_color, drag=0.0):
        """A single stationary glow -- muzzle flashes, explosion cores."""
        self.add(Particle(pos[0], pos[1], 0.0, 0.0, life, size, color, GLOW,
                          drag=drag, end_size=end_size, end_color=end_color))

    def fireball(self, pos, count=48):
        """Explosion core: fast bright particles that redden as they expand."""
        r = self.rng
        for _ in range(count):
            ang = r.uniform(0, math.tau)
            # Square-rooted speed spreads particles through the volume rather
            # than bunching them all on the leading edge.
            spd = 160 + 640 * math.sqrt(r.random())
            self.add(Particle(
                pos[0] + r.uniform(-6, 6), pos[1] + r.uniform(-6, 6),
                math.cos(ang) * spd, math.sin(ang) * spd,
                r.uniform(0.3, 0.85), r.uniform(14, 30),
                # Start orange: dozens of additive particles blow out to white
                # on their own where the fireball is densest.
                (255, 168, 56), GLOW, drag=2.6, end_size=r.uniform(3, 10),
                end_color=(138, 16, 4),
            ))

    def smoke_cloud(self, pos, count=18):
        r = self.rng
        for _ in range(count):
            ang = r.uniform(0, math.tau)
            spd = r.uniform(20, 180)
            self.add(Particle(
                pos[0] + r.uniform(-14, 14), pos[1] + r.uniform(-14, 14),
                math.cos(ang) * spd, math.sin(ang) * spd - r.uniform(10, 50),
                r.uniform(1.1, 2.4), r.uniform(16, 30), (52, 46, 43), SMOKE,
                drag=1.1, end_size=r.uniform(60, 110), alpha=0.42,
            ))

    def water(self, pos, count=6):
        r = self.rng
        for _ in range(count):
            ang = r.uniform(0, math.tau)
            spd = r.uniform(30, 190)
            self.add(Particle(
                pos[0], pos[1], math.cos(ang) * spd, math.sin(ang) * spd,
                r.uniform(0.3, 0.8), r.uniform(2, 5),
                r.choice([(198, 232, 255), (245, 250, 255), (150, 205, 245)]), DROP,
                grav=760.0, drag=0.9,
            ))

    def paint_spatter(self, pos, color, count=5):
        r = self.rng
        for _ in range(count):
            ang = r.uniform(0, math.tau)
            spd = r.uniform(40, 240)
            self.add(Particle(
                pos[0], pos[1], math.cos(ang) * spd, math.sin(ang) * spd,
                r.uniform(0.25, 0.7), r.uniform(2, 5), color, DROP,
                grav=880.0, drag=0.8,
            ))

    # -- simulation --------------------------------------------------------
    def update(self, dt: float, bounds: tuple[int, int]) -> None:
        w, h = bounds
        alive = []
        for p in self.items:
            p.life -= dt
            if p.life <= 0.0:
                continue
            if p.drag:
                damp = max(0.0, 1.0 - p.drag * dt)
                p.vx *= damp
                p.vy *= damp
            if p.grav:
                p.vy += p.grav * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.rot += p.vrot * dt
            if -80 <= p.x <= w + 80 and p.y <= h + 80:
                alive.append(p)
        self.items = alive

    # -- rendering ---------------------------------------------------------
    def draw(self, surf: pygame.Surface, offset: tuple[float, float] = (0, 0)) -> None:
        ox, oy = offset
        add = pygame.BLEND_RGB_ADD
        for p in self.items:
            t = 1.0 - (p.life / p.max_life)
            x, y = p.x + ox, p.y + oy
            size = _lerp(p.size, p.end_size, t)
            if size < 0.6:
                continue

            if p.kind == GLOW:
                fade = (1.0 - t) ** 0.65
                col = (
                    _lerp(p.color[0], p.end_color[0], t) * fade,
                    _lerp(p.color[1], p.end_color[1], t) * fade,
                    _lerp(p.color[2], p.end_color[2], t) * fade,
                )
                r = max(1, int(size))
                sprite = glow_sprite(r, col)
                surf.blit(sprite, (x - r, y - r), special_flags=add)

            elif p.kind == SMOKE:
                r = max(2, int(size))
                shade = int(_lerp(p.color[0], p.end_color[0], t))
                sprite = tinted_smoke(r, shade)
                sprite.set_alpha(int(max(0, min(255, 255 * p.alpha * (1.0 - t) ** 1.3))))
                surf.blit(sprite, (x - r, y - r))

            elif p.kind == CHUNK:
                half = size
                c, s = math.cos(p.rot), math.sin(p.rot)
                pts = [
                    (x + (-half * c - -half * s), y + (-half * s + -half * c)),
                    (x + (half * c - -half * s), y + (half * s + -half * c)),
                    (x + (half * c - half * s), y + (half * s + half * c)),
                    (x + (-half * c - half * s), y + (-half * s + half * c)),
                ]
                fade = (1.0 - t * 0.5)
                col = tuple(max(0, min(255, int(ch * fade))) for ch in p.color)
                pygame.draw.polygon(surf, col, pts)

            else:  # DROP
                fade = (1.0 - t * 0.4)
                col = tuple(max(0, min(255, int(ch * fade))) for ch in p.color)
                pygame.draw.circle(surf, col, (int(x), int(y)), max(1, int(size)))
