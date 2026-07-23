"""Shared explosion: the damage, the particles, and the on-screen aftermath.

Both the thrown grenade and the remote bomb detonate identically -- only what
triggers them differs -- so the blast lives here rather than in either tool.
"""

from __future__ import annotations

import pygame

from . import decals

BLAST = 165.0            # reference radius; tools scale it
FLASH_TIME = 0.14
WAVE_TIME = 0.55


class BlastFX:
    """Expanding shockwave rings plus the whole-screen flash.

    Kept separate from the tools because these outlive whatever set them off:
    a grenade is gone the instant it explodes, but its shockwave is not.
    """

    def __init__(self):
        self.waves: list[list] = []      # [pos, t]
        self.flash = 0.0

    def add(self, pos, intensity: float = 1.0) -> None:
        self.waves.append([pos, 0.0])
        # Take the strongest pending flash rather than restarting it. A chain of
        # twenty blasts would otherwise hold the screen at full white throughout.
        self.flash = max(self.flash, FLASH_TIME * min(1.0, intensity))

    def clear(self) -> None:
        self.waves.clear()
        self.flash = 0.0

    def update(self, dt: float) -> None:
        self.flash = max(0.0, self.flash - dt)
        for wave in list(self.waves):
            wave[1] += dt / WAVE_TIME
            if wave[1] >= 1.0:
                self.waves.remove(wave)

    def draw(self, surf: pygame.Surface, offset, blast: float = BLAST) -> None:
        ox, oy = offset
        for pos, t in self.waves:
            radius = int(30 + t * blast * 2.1)
            fade = (1.0 - t) ** 1.6
            width = max(1, int(11 * fade))
            ring = pygame.Surface((radius * 2 + 8, radius * 2 + 8), pygame.SRCALPHA)
            c = (radius + 4, radius + 4)
            pygame.draw.circle(ring, (255, 228, 180, int(190 * fade)), c, radius, width)
            pygame.draw.circle(ring, (255, 150, 60, int(120 * fade)), c,
                               max(1, radius - width), max(1, width // 2))
            surf.blit(ring, (pos[0] + ox - c[0], pos[1] + oy - c[1]))

        if self.flash > 0.0:
            k = self.flash / FLASH_TIME
            level = int(44 * k * k)
            if level > 0:
                surf.fill((level, int(level * 0.9), int(level * 0.72)),
                          special_flags=pygame.BLEND_RGB_ADD)


def detonate(ctx, pos, fx: BlastFX | None = None,
             scale: float = 1.0, volume: float = 1.0) -> None:
    """Blow a hole in the desktop at `pos`.

    `volume` is turned down by chained blasts -- twenty bombs at full volume
    clip the mixer into mush instead of sounding twenty times as good.
    """
    r = ctx.rng
    decals.explosion_crater(ctx.world, pos, int(BLAST * scale * r.uniform(0.85, 1.1)), r)

    ctx.particles.add_glow(pos, size=112 * scale, end_size=20, life=0.16,
                           color=(255, 238, 200), end_color=(255, 120, 30))
    ctx.particles.fireball(pos, count=int(54 * scale))
    ctx.particles.burst_debris(pos, count=int(38 * scale), speed=(220, 1150))
    ctx.particles.burst_glass(pos, count=int(26 * scale))
    ctx.particles.burst_sparks(pos, count=int(34 * scale), speed=(180, 900),
                               color=(255, 214, 140), life=(0.25, 0.85))
    ctx.particles.smoke_cloud(pos, count=int(20 * scale))

    # A blast lights any gasoline caught in it -- the whole point of pouring --
    # and shakes loose any shuriken or kunai stuck nearby.
    if getattr(ctx, "fire", None) is not None:
        ctx.fire.ignite(pos, BLAST * scale * 0.85, ctx)
        ctx.fire.dislodge(pos, BLAST * scale)
    # ...and incinerates any bugs inside it.
    if getattr(ctx, "bugs", None) is not None:
        ctx.bugs.hit(ctx, pos, BLAST * scale * 0.9, "burn")

    if fx is not None:
        fx.add(pos, intensity=volume)
    ctx.shake(min(1.0, 0.9 * scale))
    ctx.audio.play("explode", volume=volume)
