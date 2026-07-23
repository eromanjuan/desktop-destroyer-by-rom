"""Permanent damage painted onto the working screenshot.

Everything here mutates `world` in place. `world` is an opaque Surface (a copy
of the capture) rather than a separate alpha layer, so the per-frame cost stays
at one fast blit no matter how much damage has accumulated. The pristine
capture is kept aside purely so the washer can restore from it.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pygame

_wash_masks: dict[int, pygame.Surface] = {}
_soot_sprites: list[pygame.Surface] = []


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _jagged(rng: random.Random, start, angle, length, steps=6, wobble=0.42):
    """Walk outward from `start`, veering randomly -- a crack, basically."""
    pts = [start]
    x, y = start
    seg = length / steps
    for _ in range(steps):
        angle += rng.uniform(-wobble, wobble)
        x += math.cos(angle) * seg
        y += math.sin(angle) * seg
        pts.append((x, y))
    return pts


def _along(pts, frac: float):
    """Point at `frac` (0..1) of the way along a polyline."""
    f = max(0.0, min(1.0, frac)) * (len(pts) - 1)
    i = min(len(pts) - 2, int(f))
    t = f - i
    return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t,
            pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t)


def _irregular(rng: random.Random, center, radius, lo=0.7, hi=1.0, points=11):
    """Rough circle -- torn edges instead of a clean vector disc."""
    out = []
    for i in range(points):
        a = i * (math.tau / points)
        rr = radius * rng.uniform(lo, hi)
        out.append((center[0] + math.cos(a) * rr, center[1] + math.sin(a) * rr))
    return out


def _soot(index: int) -> pygame.Surface:
    """Irregular dark blob used to build up burn marks."""
    while len(_soot_sprites) <= index:
        i = len(_soot_sprites)
        size = 128
        r = size / 2
        yy, xx = np.mgrid[0:size, 0:size]
        dx, dy = xx - r + 0.5, yy - r + 0.5
        dist = np.sqrt(dx * dx + dy * dy) / r
        ang = np.arctan2(dy, dx)

        gen = np.random.default_rng(9000 + i)
        wob = np.zeros_like(ang, dtype=np.float32)
        for k in (2, 3, 5, 8):
            wob += gen.uniform(0.05, 0.13) * np.sin(k * ang + gen.uniform(0, math.tau))

        edge = np.clip(0.80 + wob, 0.25, 1.0)
        # Low exponent keeps the blob solid most of the way out, so burns read
        # as char with a ragged border rather than a soft grey smudge.
        alpha = np.clip((edge - dist) / (edge * 0.55), 0.0, 1.0) ** 0.9
        alpha *= gen.uniform(0.80, 1.0, alpha.shape)

        rgba = np.zeros((size, size, 4), np.uint8)
        rgba[:, :, 0] = 20
        rgba[:, :, 1] = 15
        rgba[:, :, 2] = 14
        rgba[:, :, 3] = (alpha * 255).astype(np.uint8)
        _soot_sprites.append(
            pygame.image.frombuffer(
                np.ascontiguousarray(rgba), (size, size), "RGBA"
            ).convert_alpha()
        )
    return _soot_sprites[index]


def _wash_mask(radius: int) -> pygame.Surface:
    """White disc whose alpha fades to nothing at the rim.

    Multiplied into a patch of the pristine capture so restoring blends softly
    instead of stamping a hard-edged circle.
    """
    surf = _wash_masks.get(radius)
    if surf is None:
        if len(_wash_masks) > 120:
            _wash_masks.clear()
        size = radius * 2
        yy, xx = np.mgrid[0:size, 0:size]
        dist = np.sqrt((xx - radius + 0.5) ** 2 + (yy - radius + 0.5) ** 2) / radius
        alpha = np.clip((1.0 - dist) * 2.1, 0.0, 1.0) ** 1.2
        rgba = np.full((size, size, 4), 255, np.uint8)
        rgba[:, :, 3] = (alpha * 255).astype(np.uint8)
        surf = pygame.image.frombuffer(
            np.ascontiguousarray(rgba), (size, size), "RGBA"
        ).convert_alpha()
        _wash_masks[radius] = surf
    return surf


# --------------------------------------------------------------------------
# decals
# --------------------------------------------------------------------------
def impact_crack(world: pygame.Surface, pos, radius: int, rng: random.Random) -> None:
    """Hammer hit: shattered safety glass.

    Built the way real glass breaks -- radial cracks from the impact point,
    joined by concentric rings, with the shards between them catching light
    slightly differently. Straight-ish rays and the rings are what stop this
    reading as a scribble.
    """
    radius = int(radius)
    size = radius * 2
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = (radius, radius)

    arms = rng.randint(11, 16)
    base = rng.uniform(0, math.tau)
    rays = [
        _jagged(rng, c, base + i * (math.tau / arms) + rng.uniform(-0.10, 0.10),
                radius * rng.uniform(0.66, 1.0), steps=4, wobble=0.14)
        for i in range(arms)
    ]

    # Shards: alternating faint light/dark facets between neighbouring rays.
    for i in range(arms):
        a, b = rays[i], rays[(i + 1) % arms]
        facet = [c] + a[1:] + b[1:][::-1]
        pygame.draw.polygon(s, rng.choice([(0, 0, 0, 30), (255, 255, 255, 26),
                                           (0, 0, 0, 16), (255, 255, 255, 14)]), facet)

    # Concentric rings tie the rays together -- the spiderweb signature.
    for frac in (0.36, 0.62, 0.88):
        ring = [_along(r, frac * rng.uniform(0.9, 1.08)) for r in rays]
        pygame.draw.lines(s, (20, 19, 22, 165), True, ring, 2)
        pygame.draw.lines(s, (240, 246, 255, 60), True,
                          [(x + 1, y + 1) for x, y in ring], 1)

    # Radial cracks, thicker near the impact where the glass took the load.
    for pts in rays:
        pygame.draw.lines(s, (16, 15, 18, 225), False, pts, 2)
        pygame.draw.lines(s, (16, 15, 18, 235), False, pts[:3], 3)
        pygame.draw.lines(s, (240, 246, 255, 75), False,
                          [(x + 1, y + 1) for x, y in pts], 1)

    # Pulverised core.
    pygame.draw.polygon(s, (24, 22, 26, 210), _irregular(rng, c, radius * 0.22))
    pygame.draw.polygon(s, (8, 8, 10, 255), _irregular(rng, c, radius * 0.12))

    world.blit(s, (pos[0] - radius, pos[1] - radius))


def bullet_hole(world: pygame.Surface, pos, radius: int, rng: random.Random) -> None:
    """Punched hole: black core, torn rim, short splinter cracks."""
    radius = int(radius)
    size = radius * 3          # room for the bruise and splinters around the hole
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = (size // 2, size // 2)

    # Splinters first, so the hole itself sits cleanly on top of them.
    for _ in range(rng.randint(4, 7)):
        pts = _jagged(rng, c, rng.uniform(0, math.tau),
                      radius * rng.uniform(0.55, 0.95), steps=3, wobble=0.34)
        pygame.draw.lines(s, (26, 24, 26, 130), False, pts, 1)

    pygame.draw.polygon(s, (40, 36, 36, 105), _irregular(rng, c, radius * 1.05, 0.8, 1.0))
    pygame.draw.polygon(s, (22, 20, 21, 190), _irregular(rng, c, radius * 0.74, 0.82, 1.0))
    pygame.draw.polygon(s, (5, 5, 6, 255), _irregular(rng, c, radius * 0.48, 0.82, 1.0))

    # Lit lip on the upper-left, as if the material curled out toward a light.
    pygame.draw.arc(s, (236, 240, 248, 58),
                    pygame.Rect(c[0] - radius * 0.62, c[1] - radius * 0.62,
                                radius * 1.24, radius * 1.24),
                    0.6, 3.1, 2)

    world.blit(s, (pos[0] - size // 2, pos[1] - size // 2))


def scorch(world: pygame.Surface, pos, radius: int, rng: random.Random, strength: int = 26) -> None:
    """Accumulating burn mark. Repeated passes darken toward pure char."""
    radius = max(4, int(radius))
    sprite = _soot(rng.randrange(6))
    scaled = pygame.transform.rotozoom(sprite, rng.uniform(0, 360), (radius * 2) / 128)
    scaled.set_alpha(max(1, min(255, strength)))
    rect = scaled.get_rect(center=(int(pos[0]), int(pos[1])))
    world.blit(scaled, rect)


def draw_arrow(surf: pygame.Surface, tip, angle: float, length: float,
               scale: float = 1.0, color=(126, 84, 48), shadow: bool = False,
               head: bool = True, char: float = 0.0) -> None:
    """Draw an arrow with its head at `tip`, shaft running out at `angle` deg.

    Shared by the arrow in flight and the one left stuck in the screen, so a
    loosed arrow and a planted one are unmistakably the same object. Pass
    `head=False` once it has landed -- the point is buried in the surface, and
    drawing it anyway makes the arrow look like it is lying on the screen.
    `char` (0..1) blackens the whole arrow as it burns, so a lit arrow reads as
    charred wood rather than fresh.
    """
    def _burn(rgb):
        # Lerp toward near-black soot as char rises. Clamped so a caller passing
        # a char outside 0..1 can never produce an out-of-range colour (that
        # crashed pygame when a burning arrow's char briefly went negative).
        return tuple(max(0, min(255, int(v + (24 - v) * char))) for v in rgb)

    rad = math.radians(angle)
    dx, dy = math.cos(rad), math.sin(rad)
    px, py = -dy, dx                      # perpendicular, for fletching + head
    tail = (tip[0] + dx * length, tip[1] + dy * length)
    color = _burn(color)

    if shadow:
        # Short and faint: a long opaque one reads as a second object lying
        # next to the arrow rather than as its shadow.
        ox, oy = 7 * scale, 9 * scale
        s_tail = (tip[0] + dx * length * 0.72, tip[1] + dy * length * 0.72)
        pygame.draw.line(surf, (0, 0, 0, 52),
                         (tip[0] + ox, tip[1] + oy),
                         (s_tail[0] + ox, s_tail[1] + oy), max(2, int(5 * scale)))

    w = max(1, int(5 * scale))
    pygame.draw.line(surf, _burn((58, 38, 22)), tip, tail, w + 2)
    pygame.draw.line(surf, color, tip, tail, w)
    # Highlight along the top of the shaft (an ember glow once it is charring).
    hi = (255, 150, 60) if char > 0.15 else (186, 142, 92)
    pygame.draw.line(surf, hi,
                     (tip[0] + px * scale, tip[1] + py * scale),
                     (tail[0] + px * scale, tail[1] + py * scale), max(1, int(scale)))

    # Steel head, outlined so it stays a readable shape on a pale desktop.
    if head:
        hl = 14 * scale
        hw = 5.5 * scale
        point = [
            tip,
            (tip[0] + dx * hl + px * hw, tip[1] + dy * hl + py * hw),
            (tip[0] + dx * hl - px * hw, tip[1] + dy * hl - py * hw),
        ]
        pygame.draw.polygon(surf, (188, 194, 206), point)
        pygame.draw.polygon(surf, (72, 76, 86), point, 1)

    # Fletching: two slim vanes swept back along the shaft. They must stay thin
    # and asymmetric -- fat symmetric ones read as a second arrowhead.
    vane_len = 22 * scale
    forward = (tail[0] - dx * vane_len, tail[1] - dy * vane_len)
    for side, tint in ((1, (214, 62, 54)), (-1, (232, 232, 238))):
        bulge = 6.5 * scale * side
        mid = (tail[0] - dx * vane_len * 0.55 + px * bulge,
               tail[1] - dy * vane_len * 0.55 + py * bulge)
        pygame.draw.polygon(surf, _burn(tint), [tail, mid, forward])

    # Nock.
    pygame.draw.line(surf, _burn((38, 26, 16)), tail,
                     (tail[0] + dx * 3 * scale, tail[1] + dy * 3 * scale), w)


def stuck_arrow(world: pygame.Surface, pos, angle: float, length: float,
                rng: random.Random) -> None:
    """Plant an arrow permanently in the desktop, shadow and all."""
    pad = int(length + 60)
    s = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
    c = (pad, pad)
    draw_arrow(s, c, angle, length, scale=1.0, shadow=True, head=False)
    world.blit(s, (pos[0] - pad, pos[1] - pad))


def slash(world: pygame.Surface, p0, p1, rng: random.Random, width: float = 8.0) -> None:
    """A clean cut between two points.

    Drawn as a lens -- widest in the middle, tapering to nothing at both ends --
    because a sword enters, bites deepest mid-stroke, and exits. A uniform
    rectangle reads as a drawn line instead of a cut.
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    if length < 4.0:
        return
    ux, uy = dx / length, dy / length
    px, py = -uy, ux

    pad = int(width * 4 + 14)
    size = (int(length + pad * 2), int(width * 6 + pad))
    s = pygame.Surface(size, pygame.SRCALPHA)
    ax, ay = pad, size[1] // 2                       # p0 in local space
    bx, by = pad + length * 1.0, size[1] // 2

    # Local frame: the cut runs straight along +x, then we rotate at the end.
    steps = max(6, int(length / 9))
    top, bottom = [], []
    for i in range(steps + 1):
        t = i / steps
        x = ax + (bx - ax) * t
        taper = math.sin(math.pi * t) ** 0.7          # fat middle, sharp ends
        w = width * 0.5 * taper * rng.uniform(0.88, 1.12)
        top.append((x, ay - w))
        bottom.append((x, ay + w))

    pygame.draw.polygon(s, (12, 11, 14, 245), top + bottom[::-1])
    # Lit upper lip and shadowed lower one: the surface has parted.
    pygame.draw.lines(s, (246, 250, 255, 130), False, [(x, y - 1) for x, y in top], 1)
    pygame.draw.lines(s, (0, 0, 0, 120), False, [(x, y + 1) for x, y in bottom], 1)

    # Hairline splits running off the cut.
    for _ in range(rng.randint(3, 7)):
        t = rng.uniform(0.15, 0.85)
        x = ax + (bx - ax) * t
        side = rng.choice((-1, 1))
        y = ay + side * width * 0.5
        pygame.draw.line(s, (18, 17, 20, 150), (x, y),
                         (x + rng.uniform(-9, 9), y + side * rng.uniform(5, 16)), 1)

    angle = -math.degrees(math.atan2(dy, dx))
    rotated = pygame.transform.rotate(s, angle)
    offset = pygame.math.Vector2(ax - size[0] / 2.0, ay - size[1] / 2.0).rotate(-angle)
    rect = rotated.get_rect(center=(p0[0] - offset.x, p0[1] - offset.y))
    world.blit(rotated, rect)


def explosion_crater(world: pygame.Surface, pos, radius: int, rng: random.Random) -> None:
    """Everything a grenade leaves behind, in one call.

    Layered deliberately: a solid burnt core, streaks thrown outward from it,
    structural cracking, then shrapnel punctures scattered furthest out. Built
    from the existing decals so a crater matches the rest of the damage.
    """
    radius = int(radius)

    # Burnt core -- several overlapping stamps so it reads as solid char.
    for _ in range(7):
        ang = rng.uniform(0, math.tau)
        off = rng.uniform(0, radius * 0.35)
        p = (pos[0] + math.cos(ang) * off, pos[1] + math.sin(ang) * off)
        scorch(world, p, int(radius * rng.uniform(0.45, 0.75)), rng,
               strength=rng.randint(90, 150))

    # Soot thrown outward along radial streaks, fading with distance.
    for _ in range(rng.randint(10, 16)):
        ang = rng.uniform(0, math.tau)
        dist = radius * rng.uniform(0.5, 1.25)
        steps = max(1, int(dist / 14))
        for i in range(steps):
            f = i / steps
            p = (pos[0] + math.cos(ang) * f * dist, pos[1] + math.sin(ang) * f * dist)
            scorch(world, p, max(3, int(radius * 0.22 * (1.0 - f * 0.6))), rng,
                   strength=max(6, int(70 * (1.0 - f))))

    impact_crack(world, pos, int(radius * 0.8), rng)

    for _ in range(rng.randint(12, 20)):
        ang = rng.uniform(0, math.tau)
        d = radius * rng.uniform(0.3, 1.4)
        p = (pos[0] + math.cos(ang) * d, pos[1] + math.sin(ang) * d)
        bullet_hole(world, p, rng.randint(5, 12), rng)


def nuke_crater(world: pygame.Surface, pos, radius: int, rng: random.Random) -> None:
    """A nuke's devastation: a huge charred, cratered, cracked region.

    Built from the smaller decals at scale so it matches the rest of the damage,
    but layered dense enough to obliterate a big chunk of the screen -- solid
    black core, radial cracks reaching to the rim, shrapnel pits throughout, and
    a ragged scorched edge that fades into clean screen.
    """
    radius = int(radius)

    # Fill the disc with overlapping soot, densest and blackest at the centre.
    rings = max(8, radius // 22)
    for ring in range(rings, 0, -1):
        rr = radius * ring / rings
        n = max(3, int(ring * 1.6))
        for _ in range(n):
            a = rng.uniform(0, math.tau)
            d = rng.uniform(0, rr)
            edge = d / radius                      # 0 centre .. 1 rim
            strength = int(150 * (1.0 - edge) + 30)
            scorch(world, (pos[0] + math.cos(a) * d, pos[1] + math.sin(a) * d),
                   int(radius * rng.uniform(0.10, 0.20)), rng, strength=strength)

    # Cratered core with big radial cracks fracturing outward.
    impact_crack(world, pos, int(radius * 0.55), rng)
    for _ in range(rng.randint(14, 22)):
        ang = rng.uniform(0, math.tau)
        pts = _jagged(rng, pos, ang, radius * rng.uniform(0.7, 1.05), steps=6, wobble=0.16)
        s = pygame.Surface(world.get_size(), pygame.SRCALPHA)
        pygame.draw.lines(s, (10, 9, 11, 220), False, pts, rng.randint(2, 4))
        world.blit(s, (0, 0))

    # Shrapnel pits scattered across the whole blast.
    for _ in range(rng.randint(30, 46)):
        a = rng.uniform(0, math.tau)
        d = radius * rng.uniform(0.15, 1.0)
        bullet_hole(world, (pos[0] + math.cos(a) * d, pos[1] + math.sin(a) * d),
                    rng.randint(6, 16), rng)

    # Molten-looking rim: a broken ring of hot scorch just inside the edge.
    for _ in range(int(radius / 3)):
        a = rng.uniform(0, math.tau)
        d = radius * rng.uniform(0.85, 1.05)
        scorch(world, (pos[0] + math.cos(a) * d, pos[1] + math.sin(a) * d),
               int(radius * 0.12), rng, strength=rng.randint(40, 80))


def paint_stamp(world: pygame.Surface, pos, radius: int, color, alpha: int = 235) -> None:
    radius = max(1, int(radius))
    size = radius * 2
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color, alpha), (radius, radius), radius)
    world.blit(s, (pos[0] - radius, pos[1] - radius))


def soft_restore(world: pygame.Surface, pristine: pygame.Surface, pos, radius: int) -> None:
    """Blend a soft-edged patch of the original capture back over the damage."""
    radius = max(2, int(radius))
    box = pygame.Rect(int(pos[0]) - radius, int(pos[1]) - radius, radius * 2, radius * 2)
    clipped = box.clip(world.get_rect())
    if clipped.width <= 0 or clipped.height <= 0:
        return

    patch = pristine.subsurface(clipped).copy().convert_alpha()
    local = pygame.Rect(clipped.x - box.x, clipped.y - box.y, clipped.width, clipped.height)
    patch.blit(_wash_mask(radius), (0, 0), area=local, special_flags=pygame.BLEND_RGBA_MULT)
    world.blit(patch, clipped.topleft)
