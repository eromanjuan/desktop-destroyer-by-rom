"""Gasoline, fire, and the flammable things fire spreads to.

Some things on the screen outlive the tool that made them and must react to fire
started by a *different* tool: a poured gasoline slick, an arrow stuck in the
display, a planted remote-bomb charge. A tool is deactivated the moment you
switch away from it, so none of that can live inside a tool -- it lives here, in
one system the App ticks every frame and every tool reaches through
ToolContext.fire.

That single owner makes the cross-tool chemistry fall out naturally:

    * pour gasoline, then sweep the flamethrower over it -> the slick lights and
      the fire races along the trail like a fuse
    * an arrow stuck in the screen catches, chars, and topples out of the display
    * a blast (grenade, bomb, missile) or spreading fire that reaches a planted
      remote bomb sets it off with no remote needed -- and that blast sets off the
      next bomb, and the next

Everything burns for a while, throws flame, and leaves a permanent scorch.
"""

from __future__ import annotations

import math

import pygame

from .explosion import BlastFX, detonate

# -- gasoline ---------------------------------------------------------------
MAX_PUDDLES = 260
POUR_R = (16.0, 22.0)
MAX_R = 36.0
MERGE_FRAC = 0.7
BURN_TIME = (6.0, 11.0)
SPREAD_GAP = 16.0
SPREAD_DELAY = (0.10, 0.42)
FLAME_RATE = 34.0
SCORCH_EVERY = 0.16
WET, PENDING, BURNING, SPENT = 0, 1, 2, 3

# -- stuck arrows -----------------------------------------------------------
ARROW_BURN = (2.2, 3.6)   # seconds an arrow flames before it topples
ARROW_FALL = 0.9          # seconds to tip out of the screen
A_STUCK, A_BURNING, A_FALLING, A_GONE = 0, 1, 2, 3

# -- embedded metal projectiles (shuriken / kunai) --------------------------
P_STUCK, P_FALLING = 0, 1
PIN_FALL = 1.0            # seconds a dislodged pin takes to tumble away

# -- remote-bomb charges ----------------------------------------------------
CHARGE_FUSE_R = 24.0      # fire this close to a charge sets it off
CHAIN_STAGGER = 0.07

_wet_cache: dict[int, pygame.Surface] = {}
_ember_cache: dict[int, pygame.Surface] = {}


def _wet_sprite(r: int) -> pygame.Surface:
    """Dark reflective puddle with a faint petrol-sheen rim and a glint."""
    r = max(3, min(int(MAX_R) + 2, int(r)))
    surf = _wet_cache.get(r)
    if surf is None:
        if len(_wet_cache) > 80:
            _wet_cache.clear()
        size = r * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        steps = max(6, r // 2)
        for i in range(steps, 0, -1):
            t = i / steps
            a = int(150 * (1.0 - t) + 40)
            pygame.draw.circle(surf, (16, 15, 22, a), (r, r), int(r * t))
        pygame.draw.circle(surf, (120, 60, 130, 45), (r, r), int(r * 0.82), 2)
        pygame.draw.circle(surf, (60, 120, 120, 40), (r, r), int(r * 0.7), 1)
        pygame.draw.circle(surf, (200, 205, 220, 70),
                           (int(r * 0.66), int(r * 0.6)), max(1, r // 6))
        _wet_cache[r] = surf
    return surf


def _ember_sprite(r: int) -> pygame.Surface:
    """Additive glow drawn under the flames so the puddle floor reads as lit."""
    r = max(3, min(int(MAX_R) + 6, int(r)))
    surf = _ember_cache.get(r)
    if surf is None:
        if len(_ember_cache) > 80:
            _ember_cache.clear()
        size = r * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        steps = max(6, r // 2)
        for i in range(steps, 0, -1):
            t = i / steps
            pygame.draw.circle(
                surf,
                (min(255, int(255 * (1 - t) + 40)), min(255, int(120 * (1 - t) + 20)),
                 20, min(255, int(90 * (1 - t) + 10))),
                (r, r), int(r * t))
        _ember_cache[r] = surf
    return surf


class Puddle:
    __slots__ = ("x", "y", "r", "state", "ignite_in", "burn_left",
                 "emit_debt", "scorch_t", "flick")

    def __init__(self, x, y, r):
        self.x, self.y, self.r = x, y, r
        self.state = WET
        self.ignite_in = 0.0
        self.burn_left = 0.0
        self.emit_debt = 0.0
        self.scorch_t = 0.0
        self.flick = 0.0


class StuckArrow:
    __slots__ = ("x", "y", "ox", "oy", "angle", "length", "charge", "state",
                 "burn_left", "burn_total", "fall_t", "emit_debt", "scorch_t",
                 "flick", "vx", "vr")

    def __init__(self, x, y, angle, length, charge):
        self.x, self.y = x, y
        self.ox, self.oy = x, y        # where it was stuck -- the scar goes here
        self.angle = angle
        self.length = length
        self.charge = charge
        self.state = A_STUCK
        self.burn_left = 0.0
        self.burn_total = 1.0
        self.fall_t = 0.0
        self.emit_debt = 0.0
        self.scorch_t = 0.0
        self.flick = 0.0
        self.vx = 0.0
        self.vr = 0.0


class Charge:
    __slots__ = ("x", "y", "age", "triggered")

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.age = 0.0
        self.triggered = False


class Pin:
    """A shuriken or kunai embedded in the screen -- knocked loose by a hammer
    blow or a blast, then it tumbles off and falls away."""

    __slots__ = ("kind", "x", "y", "angle", "state", "fall_t", "vx", "vy", "vr")

    def __init__(self, kind, x, y, angle):
        self.kind = kind        # "star" | "kunai"
        self.x, self.y = x, y
        self.angle = angle
        self.state = P_STUCK
        self.fall_t = 0.0
        self.vx = self.vy = self.vr = 0.0


class FireSystem:
    def __init__(self, rng):
        self.rng = rng
        self.puddles: list[Puddle] = []
        self.arrows: list[StuckArrow] = []
        self.pins: list[Pin] = []
        self.charges: list[Charge] = []
        self.pending: list[list] = []      # [pos, delay] -- charge detonations
        self.blast_fx = BlastFX()
        self._loop_on = False

    # -- queries -----------------------------------------------------------
    def __len__(self):
        return len(self.puddles)

    @property
    def charge_count(self) -> int:
        return len(self.charges)

    @property
    def any_burning(self) -> bool:
        return (any(p.state in (BURNING, PENDING) for p in self.puddles)
                or any(a.state == A_BURNING for a in self.arrows))

    @property
    def has_fuel(self) -> bool:
        return any(p.state == WET for p in self.puddles)

    def is_burning_near(self, x, y, extra=0.0) -> bool:
        """Public check used by the bug system to torch bugs that walk into fire."""
        return self._burning_near(x, y, extra)

    def _burning_near(self, x, y, extra=0.0) -> bool:
        for p in self.puddles:
            if p.state == BURNING and math.hypot(p.x - x, p.y - y) <= p.r + extra:
                return True
        for a in self.arrows:
            if a.state == A_BURNING and math.hypot(a.x - x, a.y - y) <= 18 + extra:
                return True
        return False

    # -- adding entities ---------------------------------------------------
    def pour(self, pos, rng) -> None:
        """Add fuel at `pos`, merging into a touching wet blob so a dragged
        pour reads as one connected slick rather than a string of dots."""
        x, y = pos
        for p in self.puddles:
            if p.state != WET:
                continue
            if math.hypot(p.x - x, p.y - y) < p.r * MERGE_FRAC:
                if p.r < MAX_R:
                    p.r = min(MAX_R, p.r + 1.6)
                p.x += (x - p.x) * 0.25
                p.y += (y - p.y) * 0.25
                return
        if len(self.puddles) < MAX_PUDDLES:
            self.puddles.append(Puddle(x, y, rng.uniform(*POUR_R)))

    def add_arrow(self, pos, angle, length, charge) -> None:
        self.arrows.append(StuckArrow(pos[0], pos[1], angle, length, charge))

    def add_charge(self, pos) -> None:
        self.charges.append(Charge(pos[0], pos[1]))

    def add_pin(self, pos, angle, kind) -> None:
        """Embed a shuriken/kunai that a blow or blast can later shake loose."""
        self.pins.append(Pin(kind, pos[0], pos[1], angle))

    def dislodge(self, pos, radius: float) -> int:
        """Knock any embedded pin within `radius` loose so it tumbles and falls.
        Called by the hammer and by every blast."""
        x, y = pos
        n = 0
        for p in self.pins:
            if p.state == P_STUCK and math.hypot(p.x - x, p.y - y) <= radius:
                p.state = P_FALLING
                # Fling away from the impact, then gravity takes over.
                a = math.atan2(p.y - y, p.x - x) if (p.x, p.y) != (x, y) else self.rng.uniform(0, math.tau)
                sp = self.rng.uniform(40, 130)
                p.vx = math.cos(a) * sp + self.rng.uniform(-30, 30)
                p.vy = math.sin(a) * sp - self.rng.uniform(20, 80)
                p.vr = self.rng.uniform(-12, 12)
                n += 1
        return n

    # -- ignition ----------------------------------------------------------
    def ignite(self, pos, radius: float, ctx=None) -> bool:
        """Light every flammable within `radius` of `pos` -- gasoline and arrows
        catch fire, planted charges are set off. Called by the flamethrower and
        by every kind of blast. Returns True if anything caught."""
        x, y = pos
        lit = False
        for p in self.puddles:
            if p.state == WET and math.hypot(p.x - x, p.y - y) <= radius + p.r:
                self._light(p, delay=0.0)
                lit = True
        for a in self.arrows:
            if a.state == A_STUCK and math.hypot(a.x - x, a.y - y) <= radius + a.length:
                self._light_arrow(a)
                lit = True
        for c in self.charges:
            if not c.triggered and math.hypot(c.x - x, c.y - y) <= radius + CHARGE_FUSE_R:
                self._schedule_charge(c, self.rng.uniform(0.02, 0.16))
        if lit and ctx is not None:
            ctx.audio.play("whoosh")
        return lit

    def _light(self, p: Puddle, delay: float) -> None:
        if p.state in (BURNING, SPENT):
            return
        if p.state == PENDING and delay >= p.ignite_in:
            return
        p.state = PENDING
        p.ignite_in = delay

    def _light_arrow(self, a: StuckArrow) -> None:
        if a.state == A_STUCK:
            a.state = A_BURNING
            a.burn_left = a.burn_total = self.rng.uniform(*ARROW_BURN)
            a.scorch_t = 0.0

    def _schedule_charge(self, c: Charge, delay: float) -> None:
        if c.triggered:
            return
        c.triggered = True
        self.pending.append([(c.x, c.y), delay])

    # -- remote detonation -------------------------------------------------
    def detonate_all(self, ctx) -> bool:
        """The remote's job: set off every planted charge in a rolling chain."""
        live = [c for c in self.charges if not c.triggered]
        for i, c in enumerate(live):
            self._schedule_charge(c, i * CHAIN_STAGGER)
        # Prune now so the count reflects reality the instant the remote fires,
        # rather than one tick later.
        self.charges = [c for c in self.charges if not c.triggered]
        return bool(live)

    # -- douse -------------------------------------------------------------
    def douse(self, pos, radius: float, ctx=None) -> None:
        """Water kills fuel and fire alike. Wet fuel just vanishes; anything
        already burning is cut short (its char stays, as real burns do)."""
        x, y = pos
        touched = False
        for p in self.puddles:
            if math.hypot(p.x - x, p.y - y) > radius + p.r:
                continue
            touched = True
            if p.state == BURNING:
                p.burn_left = 0.0
            elif p.state in (WET, PENDING):
                p.state = SPENT
                p.r = 0.0
        for a in self.arrows:
            if a.state == A_BURNING and math.hypot(a.x - x, a.y - y) <= radius:
                a.burn_left = 0.0
                touched = True
        if touched and ctx is not None:
            ctx.particles.smoke_cloud((x, y), count=3)

    def clear(self) -> None:
        self.puddles.clear()
        self.arrows.clear()
        self.pins.clear()
        self.charges.clear()
        self.pending.clear()
        self.blast_fx.clear()

    # -- simulation --------------------------------------------------------
    def update(self, dt: float, ctx) -> None:
        rng = ctx.rng
        world, particles = ctx.world, ctx.particles

        self._update_gasoline(dt, ctx, rng, world, particles)
        self._update_arrows(dt, ctx, rng, world, particles)
        self._update_pins(dt, ctx)
        self._update_charges(dt, ctx, rng)
        self.blast_fx.update(dt)

        want = self.any_burning
        if want and not self._loop_on:
            ctx.audio.start_loop("burning")
            self._loop_on = True
        elif not want and self._loop_on:
            ctx.audio.stop_loop("burning")
            self._loop_on = False

    def _update_gasoline(self, dt, ctx, rng, world, particles) -> None:
        from . import decals
        burning = [p for p in self.puddles if p.state == BURNING]

        for p in self.puddles:
            if p.state == PENDING:
                p.ignite_in -= dt
                if p.ignite_in <= 0.0:
                    p.state = BURNING
                    p.burn_left = rng.uniform(*BURN_TIME)
                    p.scorch_t = 0.0

            if p.state == BURNING:
                p.flick += dt
                p.burn_left -= dt
                p.emit_debt += FLAME_RATE * (p.r / 22.0) * dt
                count = int(p.emit_debt)
                p.emit_debt -= count
                for _ in range(count):
                    a = rng.uniform(0, math.tau)
                    d = rng.uniform(0, p.r * 0.8)
                    particles.flame((p.x + math.cos(a) * d, p.y + math.sin(a) * d),
                                    drift=(0, 0), count=1)
                p.scorch_t -= dt
                if p.scorch_t <= 0.0:
                    p.scorch_t = SCORCH_EVERY
                    a = rng.uniform(0, math.tau)
                    d = rng.uniform(0, p.r * 0.6)
                    decals.scorch(world, (p.x + math.cos(a) * d, p.y + math.sin(a) * d),
                                  int(p.r * rng.uniform(0.7, 1.1)), rng,
                                  strength=rng.randint(20, 34))
                if p.burn_left <= 0.0:
                    p.state = SPENT
                    self._stamp_burn(world, p.x, p.y, p.r, rng)

        # A burning puddle lights any wet one it reaches, and any stuck arrow.
        for p in burning:
            reach = p.r + SPREAD_GAP
            for q in self.puddles:
                if q.state == WET and math.hypot(p.x - q.x, p.y - q.y) <= reach + q.r:
                    self._light(q, delay=rng.uniform(*SPREAD_DELAY))
            for a in self.arrows:
                if a.state == A_STUCK and math.hypot(p.x - a.x, p.y - a.y) <= reach + 12:
                    self._light_arrow(a)

        self.puddles = [p for p in self.puddles if p.state != SPENT]

    def _update_arrows(self, dt, ctx, rng, world, particles) -> None:
        from . import decals
        for a in self.arrows:
            if a.state == A_BURNING:
                a.flick += dt
                a.burn_left -= dt
                # Flames climb the shaft.
                a.emit_debt += 26.0 * dt
                n = int(a.emit_debt)
                a.emit_debt -= n
                rad = math.radians(a.angle)
                for _ in range(n):
                    f = rng.uniform(0.0, 1.0)
                    particles.flame((a.x + math.cos(rad) * a.length * f,
                                     a.y + math.sin(rad) * a.length * f),
                                    drift=(0, 0), count=1)
                # The wall the arrow is stuck in chars around it as it burns.
                a.scorch_t -= dt
                if a.scorch_t <= 0.0:
                    a.scorch_t = SCORCH_EVERY
                    rad = math.radians(a.angle)
                    f = rng.uniform(0.0, 0.5)
                    decals.scorch(world, (a.ox + math.cos(rad) * a.length * f,
                                          a.oy + math.sin(rad) * a.length * f),
                                  rng.randint(10, 18), rng, strength=rng.randint(24, 40))
                # A burning arrow lights gasoline it leans into.
                for p in self.puddles:
                    if p.state == WET and math.hypot(p.x - a.x, p.y - a.y) <= 22 + p.r:
                        self._light(p, delay=rng.uniform(*SPREAD_DELAY))
                if a.burn_left <= 0.0:
                    a.state = A_FALLING
                    a.vr = rng.choice((-1, 1)) * rng.uniform(90, 160)   # deg/s topple
                    a.vx = rng.uniform(-40, 40)

            elif a.state == A_FALLING:
                a.fall_t += dt
                a.x += a.vx * dt
                a.y += (a.fall_t * 900.0) * dt      # accelerating drop
                a.angle += a.vr * dt
                if a.fall_t >= ARROW_FALL:
                    a.state = A_GONE
                    # The scorched hole where it was embedded, not where it fell.
                    self._stamp_burn(world, a.ox, a.oy, 20, rng)

        self.arrows = [a for a in self.arrows if a.state != A_GONE]

    def _update_pins(self, dt, ctx) -> None:
        h = ctx.size[1]
        for p in self.pins:
            if p.state == P_FALLING:
                p.fall_t += dt
                p.vy += 1100 * dt          # gravity
                p.x += p.vx * dt
                p.y += p.vy * dt
                p.angle += p.vr * dt * 57.3
        self.pins = [p for p in self.pins
                     if not (p.state == P_FALLING and (p.fall_t > PIN_FALL or p.y > h + 40))]

    def _update_charges(self, dt, ctx, rng) -> None:
        for c in self.charges:
            c.age += dt
            if not c.triggered and self._burning_near(c.x, c.y, CHARGE_FUSE_R):
                self._schedule_charge(c, rng.uniform(0.03, 0.14))
        self.charges = [c for c in self.charges if not c.triggered]

        if self.pending:
            volume = max(0.35, 1.0 - 0.05 * len(self.pending))
            for item in list(self.pending):
                item[1] -= dt
                if item[1] <= 0.0:
                    self.pending.remove(item)
                    # This blast re-enters ignite() and can set off more charges
                    # and gasoline -- the chain reaction, with no recursion since
                    # scheduling is deferred through this same queue.
                    detonate(ctx, item[0], self.blast_fx, volume=volume)

    def _stamp_burn(self, world, x, y, r, rng) -> None:
        if r < 2:
            return
        from . import decals
        for _ in range(rng.randint(4, 7)):
            a = rng.uniform(0, math.tau)
            d = rng.uniform(0, r * 0.8)
            decals.scorch(world, (x + math.cos(a) * d, y + math.sin(a) * d),
                          int(r * rng.uniform(0.7, 1.2)), rng,
                          strength=rng.randint(70, 120))

    def stop(self, ctx) -> None:
        if self._loop_on:
            ctx.audio.stop_loop("burning")
            self._loop_on = False

    # -- rendering ---------------------------------------------------------
    def draw_ground(self, surf: pygame.Surface, offset=(0, 0)) -> None:
        """Wet gasoline and the ember floor -- drawn under the flame particles."""
        ox, oy = offset
        add = pygame.BLEND_RGB_ADD
        for p in self.puddles:
            x, y = p.x + ox, p.y + oy
            if p.state in (WET, PENDING):
                r = int(p.r)
                surf.blit(_wet_sprite(r), (x - r, y - r))
            elif p.state == BURNING:
                flick = 0.75 + 0.25 * math.sin(p.flick * 21.0)
                r = int(p.r * (1.15 + 0.12 * flick))
                spr = _ember_sprite(r)
                spr.set_alpha(int(210 * flick))
                surf.blit(spr, (x - r, y - r), special_flags=add)

    def draw_top(self, surf: pygame.Surface, offset=(0, 0)) -> None:
        """Arrows, charges and blast shockwaves -- drawn over the particles."""
        from . import decals
        from .tools.bomb import draw_charge
        ox, oy = offset

        for a in self.arrows:
            x, y = a.x + ox, a.y + oy
            if a.state == A_STUCK:
                decals.draw_arrow(surf, (x, y), a.angle, a.length, head=False)
            elif a.state == A_BURNING:
                # Char rises 0 -> ~0.95 across this arrow's own burn time.
                char = 0.95 * (1.0 - a.burn_left / a.burn_total)
                char = max(0.0, min(0.95, char))
                decals.draw_arrow(surf, (x, y), a.angle, a.length, head=False, char=char)
            elif a.state == A_FALLING:
                fade = max(0, 1.0 - a.fall_t / ARROW_FALL)
                tmp = pygame.Surface((int(a.length) + 40, int(a.length) + 40), pygame.SRCALPHA)
                c = (tmp.get_width() // 2, tmp.get_height() // 2)
                decals.draw_arrow(tmp, c, a.angle, a.length, head=False, char=0.95)
                tmp.set_alpha(int(255 * fade))
                surf.blit(tmp, (x - c[0], y - c[1]))

        for p in self.pins:
            x, y = p.x + ox, p.y + oy
            fade = 1.0 if p.state == P_STUCK else max(0.0, 1.0 - p.fall_t / PIN_FALL)
            if p.kind == "star":
                if fade >= 0.999:
                    decals.draw_shuriken(surf, x, y, math.radians(p.angle), 1.15)
                else:
                    tmp = pygame.Surface((44, 44), pygame.SRCALPHA)
                    decals.draw_shuriken(tmp, 22, 22, math.radians(p.angle), 1.15)
                    tmp.set_alpha(int(255 * fade))
                    surf.blit(tmp, (x - 22, y - 22))
            else:  # kunai
                if fade >= 0.999:
                    decals.draw_kunai(surf, (x, y), p.angle, 1.15, shadow=True)
                else:
                    tmp = pygame.Surface((80, 80), pygame.SRCALPHA)
                    decals.draw_kunai(tmp, (40, 40), p.angle, 1.15)
                    tmp.set_alpha(int(255 * fade))
                    surf.blit(tmp, (x - 40, y - 40))

        blink_on = (pygame.time.get_ticks() // 300) % 2 == 0
        for c in self.charges:
            draw_charge(surf, (c.x + ox, c.y + oy), blink_on, armed=True)

        self.blast_fx.draw(surf, offset)
