"""Bugs: ants and flies that wander the screen and die by whatever hits them.

Like the fire system, this is a persistent field the App ticks and draws every
frame, independent of the active tool -- a fly is a fly no matter what you are
holding. Any weapon kills bugs by calling `ctx.bugs.hit(ctx, pos, radius, cause)`
at its point of impact, and the `cause` decides how they die:

    "slice"  (katana, star shuriken)   -> cut clean in two, halves slide apart
    "smash"  (hammer, rock)            -> a bloody splat on the screen
    "shot"   (gun, arrow, kunai)       -> a spurt of blood, the carcass tumbles
    "burn"   (fire, flame, explosives) -> blackens, curls and drops, trailing smoke

They respawn from the edges forever, so there is always something to swat.
"""

from __future__ import annotations

import math

import pygame

ANT, FLY = 0, 1

TARGET = 22               # how many live bugs to keep around
HARD_CAP = 110            # never exceed this many live + dying
SPAWN_EVERY = 0.32        # seconds between top-ups toward TARGET
SEED = 9                  # how many appear right away so the screen is alive

# death-effect kinds
D_SLICE, D_SMASH, D_SHOT, D_BURN = 0, 1, 2, 3

ANT_COL = (78, 44, 30)
FLY_COL = (34, 34, 40)
BLOOD = (150, 12, 12)


# --------------------------------------------------------------------------
# drawing a live bug
# --------------------------------------------------------------------------
def _draw_ant(surf, x, y, ang, legphase, scale=1.0, tint=ANT_COL):
    c, s = math.cos(ang), math.sin(ang)

    def fwd(d, o=0.0):
        return (x + c * d - s * o, y + s * d + c * o)

    # Six legs, animated in a walking wiggle.
    for i, base in enumerate((3.0, 0.0, -3.0)):
        sw = math.sin(legphase + i * 1.3) * 2.4
        for side in (1, -1):
            hip = fwd(base * scale, side * 2 * scale)
            foot = fwd((base + sw) * scale, side * (6 * scale + 1))
            pygame.draw.line(surf, tint, hip, foot, max(1, int(scale)))
    # Body: abdomen, thorax, head.
    pygame.draw.circle(surf, tint, fwd(-4 * scale), max(2, int(3.2 * scale)))
    pygame.draw.circle(surf, tint, fwd(0), max(1, int(2.0 * scale)))
    pygame.draw.circle(surf, tint, fwd(4 * scale), max(1, int(2.4 * scale)))
    # Antennae.
    for side in (1, -1):
        pygame.draw.line(surf, tint, fwd(5 * scale), fwd(8 * scale, side * 2.5 * scale),
                         max(1, int(scale)))


def _draw_fly(surf, x, y, ang, wingphase, scale=1.0, tint=FLY_COL):
    c, s = math.cos(ang), math.sin(ang)

    def fwd(d, o=0.0):
        return (x + c * d - s * o, y + s * d + c * o)

    # Blurred wings flick in and out.
    spread = 3.0 + 2.5 * abs(math.sin(wingphase))
    for side in (1, -1):
        wing = pygame.Surface((int(10 * scale), int(6 * scale)), pygame.SRCALPHA)
        pygame.draw.ellipse(wing, (210, 220, 235, 120), wing.get_rect())
        wr = wing.get_rect(center=fwd(1 * scale, side * spread * scale))
        surf.blit(wing, wr)
    # Body: two dark segments.
    pygame.draw.circle(surf, tint, fwd(-2.5 * scale), max(2, int(2.6 * scale)))
    pygame.draw.circle(surf, tint, fwd(1.5 * scale), max(1, int(2.0 * scale)))
    # Red eyes.
    pygame.draw.circle(surf, (150, 40, 30), fwd(3.5 * scale), max(1, int(1.2 * scale)))


class Bug:
    __slots__ = ("type", "x", "y", "ang", "speed", "phase", "scale",
                 "turn_t", "dart_t", "vx", "vy")

    def __init__(self, btype, x, y, ang, rng):
        self.type = btype
        self.x, self.y = x, y
        self.ang = ang
        self.phase = rng.uniform(0, 6.28)
        if btype == ANT:
            self.speed = rng.uniform(34, 64)
            self.scale = rng.uniform(1.15, 1.6)
            self.turn_t = 0.0
            self.vx = self.vy = 0.0
        else:
            self.speed = rng.uniform(120, 210)
            self.scale = rng.uniform(1.05, 1.45)
            self.dart_t = 0.0
            self.vx = math.cos(ang) * self.speed
            self.vy = math.sin(ang) * self.speed
        self.turn_t = 0.0
        self.dart_t = 0.0


class Death:
    """A short-lived death animation. World decals (blood, scorch) are stamped
    at kill time; this just plays the bug's last moment on top."""

    __slots__ = ("kind", "btype", "x", "y", "ang", "t", "dur", "vx", "vy", "vr", "scale")

    def __init__(self, kind, btype, x, y, ang, scale, rng):
        self.kind = kind
        self.btype = btype
        self.x, self.y = x, y
        self.ang = ang
        self.scale = scale
        self.t = 0.0
        self.vr = rng.uniform(-8, 8)
        if kind == D_SLICE:
            self.dur = 0.5
            self.vx = rng.uniform(20, 50)      # halves push apart along the cut
            self.vy = 0.0
        elif kind == D_BURN:
            self.dur = 1.1
            self.vx = rng.uniform(-30, 30)
            self.vy = rng.uniform(40, 90)       # curls up and drops
        elif kind == D_SHOT:
            self.dur = 0.7
            self.vx = rng.uniform(-60, 60)
            self.vy = rng.uniform(-40, 20)
        else:  # D_SMASH -- decal only, this just fades a quick gib puff
            self.dur = 0.25
            self.vx = self.vy = 0.0


class BugSystem:
    def __init__(self, rng):
        self.rng = rng
        self.bugs: list[Bug] = []
        self.deaths: list[Death] = []
        self.spawn_t = 0.0
        self.auto = False        # off by default -- the player places bugs by hand
        self.target = TARGET
        self._seeded = False

    def __len__(self):
        return len(self.bugs)

    def clear(self):
        self.bugs.clear()
        self.deaths.clear()

    # -- spawning ----------------------------------------------------------
    def _spawn(self, size):
        w, h = size
        r = self.rng
        edge = r.randrange(4)
        if edge == 0:
            x, y, ang = r.uniform(0, w), -20, r.uniform(0.2, 2.94)
        elif edge == 1:
            x, y, ang = r.uniform(0, w), h + 20, r.uniform(-2.94, -0.2)
        elif edge == 2:
            x, y, ang = -20, r.uniform(0, h), r.uniform(-1.2, 1.2)
        else:
            x, y, ang = w + 20, r.uniform(0, h), r.uniform(1.94, 4.34)
        btype = ANT if r.random() < 0.55 else FLY
        self.bugs.append(Bug(btype, x, y, ang, r))

    def spawn_at(self, pos, btype) -> None:
        """Drop one bug where the player clicked (used by the Bugs tool)."""
        if len(self.bugs) < HARD_CAP:
            self.bugs.append(Bug(btype, pos[0], pos[1], self.rng.uniform(0, 6.28), self.rng))

    # -- simulation --------------------------------------------------------
    def update(self, dt: float, ctx) -> None:
        w, h = ctx.size
        r = self.rng

        # Auto-spawning is opt-in. By default bugs only exist where the player
        # placed them with the Bugs tool.
        if self.auto and not self._seeded:
            self._seeded = True
            for _ in range(min(SEED, self.target)):
                bt = ANT if r.random() < 0.55 else FLY
                self.bugs.append(Bug(bt, r.uniform(40, w - 40), r.uniform(40, h - 40),
                                     r.uniform(0, 6.28), r))
        if self.auto and len(self.bugs) < min(self.target, HARD_CAP):
            self.spawn_t -= dt
            if self.spawn_t <= 0.0:
                self.spawn_t = SPAWN_EVERY
                self._spawn(ctx.size)

        for b in self.bugs:
            b.phase += dt * (10.0 if b.type == ANT else 42.0) * (b.speed / 60.0)
            if b.type == ANT:
                b.turn_t -= dt
                if b.turn_t <= 0.0:
                    b.turn_t = r.uniform(0.3, 1.1)
                    b.ang += r.uniform(-0.9, 0.9)
                # Steer back toward the screen if wandering off.
                if b.x < 30 or b.x > w - 30 or b.y < 30 or b.y > h - 30:
                    b.ang += math.atan2((h / 2 - b.y), (w / 2 - b.x)) * 0.06
                b.x += math.cos(b.ang) * b.speed * dt
                b.y += math.sin(b.ang) * b.speed * dt
            else:  # fly -- jittery darts and hovering
                b.dart_t -= dt
                if b.dart_t <= 0.0:
                    b.dart_t = r.uniform(0.15, 0.5)
                    na = r.uniform(0, 6.28)
                    sp = b.speed * r.uniform(0.3, 1.3)
                    b.vx = math.cos(na) * sp
                    b.vy = math.sin(na) * sp
                b.vx += r.uniform(-30, 30)
                b.vy += r.uniform(-30, 30)
                if b.x < 20:
                    b.vx += 120
                elif b.x > w - 20:
                    b.vx -= 120
                if b.y < 20:
                    b.vy += 120
                elif b.y > h - 20:
                    b.vy -= 120
                b.x += b.vx * dt
                b.y += b.vy * dt
                b.ang = math.atan2(b.vy, b.vx)

        # A bug that wanders into fire burns where it stands.
        fire = getattr(ctx, "fire", None)
        if fire is not None:
            caught = [b for b in self.bugs if fire.is_burning_near(b.x, b.y, 8)]
            for b in caught:
                self._kill(ctx, b, D_BURN)
            if caught:
                caught_set = set(id(b) for b in caught)
                self.bugs = [b for b in self.bugs if id(b) not in caught_set]

        # Cull anything that wandered far off-screen (ants leaving the scene).
        self.bugs = [b for b in self.bugs
                     if -60 < b.x < w + 60 and -60 < b.y < h + 60]

        for d in self.deaths:
            d.t += dt
            d.x += d.vx * dt
            if d.kind == D_BURN:
                d.vy += 260 * dt            # gravity as it drops
            d.y += d.vy * dt
            d.ang += d.vr * dt
        self.deaths = [d for d in self.deaths if d.t < d.dur]

    # -- getting killed ----------------------------------------------------
    def hit(self, ctx, pos, radius: float, cause: str) -> int:
        """Kill every live bug within `radius` of `pos`, dying per `cause`.
        Returns how many were killed."""
        x, y = pos
        kind = {"slice": D_SLICE, "smash": D_SMASH,
                "shot": D_SHOT, "burn": D_BURN}.get(cause, D_SHOT)
        killed = 0
        survivors = []
        for b in self.bugs:
            if math.hypot(b.x - x, b.y - y) > radius:
                survivors.append(b)
                continue
            killed += 1
            self._kill(ctx, b, kind)
        self.bugs = survivors
        return killed

    def _kill(self, ctx, b: Bug, kind: int) -> None:
        from . import decals
        r = ctx.rng
        if len(self.deaths) < HARD_CAP:
            self.deaths.append(Death(kind, b.type, b.x, b.y, b.ang, b.scale, r))

        if kind == D_SMASH:
            decals.blood_splat(ctx.world, (b.x, b.y), int(6 * b.scale), r)
            ctx.particles.paint_spatter((b.x, b.y), BLOOD, count=r.randint(5, 10))
        elif kind == D_SHOT:
            decals.blood_splat(ctx.world, (b.x, b.y), int(3 * b.scale), r)
            ctx.particles.paint_spatter((b.x, b.y), BLOOD, count=r.randint(3, 6))
        elif kind == D_SLICE:
            ctx.particles.paint_spatter((b.x, b.y), BLOOD, count=r.randint(2, 5))
        elif kind == D_BURN:
            decals.scorch(ctx.world, (b.x, b.y), int(6 * b.scale), r, strength=r.randint(30, 60))
            ctx.particles.flame((b.x, b.y), drift=(0, 0), count=2)

    # -- rendering ---------------------------------------------------------
    def draw(self, surf: pygame.Surface, offset=(0, 0)) -> None:
        ox, oy = offset
        for b in self.bugs:
            x, y = b.x + ox, b.y + oy
            if b.type == FLY:
                # Little shadow under the fly to sell that it is airborne.
                sh = pygame.Surface((10, 5), pygame.SRCALPHA)
                pygame.draw.ellipse(sh, (0, 0, 0, 60), sh.get_rect())
                surf.blit(sh, (x - 5, y + 7))
                _draw_fly(surf, x, y, b.ang, b.phase, b.scale)
            else:
                _draw_ant(surf, x, y, b.ang, b.phase, b.scale)

        for d in self.deaths:
            self._draw_death(surf, d, ox, oy)

    def _draw_death(self, surf, d: Death, ox, oy) -> None:
        x, y = d.x + ox, d.y + oy
        p = d.t / d.dur
        fade = max(0, 1.0 - p)

        if d.kind == D_SLICE:
            # Two halves sliding apart along the perpendicular of the cut.
            c, s = math.cos(d.ang), math.sin(d.ang)
            px, py = -s, c
            off = d.vx * d.t
            for sign in (1, -1):
                hx, hy = x + px * off * sign, y + py * off * sign
                tmp = pygame.Surface((36, 36), pygame.SRCALPHA)
                (_draw_fly if d.btype == FLY else _draw_ant)(tmp, 18, 18, d.ang, 0, d.scale)
                # Clip to one half by covering the other with a wedge.
                cover = pygame.Surface((36, 36), pygame.SRCALPHA)
                pts = [(18, 18),
                       (18 + c * 26 - px * sign * 26, 18 + s * 26 - py * sign * 26),
                       (18 - c * 26 - px * sign * 26, 18 - s * 26 - py * sign * 26)]
                pygame.draw.polygon(cover, (0, 0, 0, 255), pts)
                tmp.blit(cover, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
                tmp.set_alpha(int(255 * fade))
                surf.blit(tmp, (hx - 18, hy - 18))

        elif d.kind == D_BURN:
            char = min(1.0, p * 1.6)
            tint = (int(70 * (1 - char) + 18), int(40 * (1 - char) + 14), 14)
            tmp = pygame.Surface((36, 36), pygame.SRCALPHA)
            (_draw_fly if d.btype == FLY else _draw_ant)(tmp, 18, 18, d.ang, 0, d.scale, tint)
            tmp.set_alpha(int(255 * fade))
            surf.blit(tmp, (x - 18, y - 18))

        elif d.kind == D_SHOT:
            tmp = pygame.Surface((36, 36), pygame.SRCALPHA)
            (_draw_fly if d.btype == FLY else _draw_ant)(tmp, 18, 18, d.ang, 0, d.scale)
            tmp.set_alpha(int(255 * fade))
            surf.blit(tmp, (x - 18, y - 18))
        # D_SMASH: nothing to draw -- the blood decal is already on the world.
