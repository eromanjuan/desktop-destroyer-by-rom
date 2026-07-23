"""Gasoline + fire regression test.

Covers the cross-tool mechanic the selftest can't: gasoline is poured by one
tool but ignited by others. Runs headless under the dummy drivers.

    python tests/test_fire.py       -> exits 0 on success, 1 on failure
"""

import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random  # noqa: E402

import pygame  # noqa: E402

from destroyer.fire import BURNING, WET, FireSystem  # noqa: E402
from destroyer.particles import ParticleSystem  # noqa: E402
from destroyer.tools import ToolContext, build_tools  # noqa: E402

DT = 1 / 60
W, H = 800, 500
failures: list[str] = []


def check(label: str, condition: bool) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    if not condition:
        failures.append(label)


def fresh():
    pygame.init()
    pygame.display.set_mode((W, H))
    rng = random.Random(5)
    pristine = pygame.Surface((W, H))
    pristine.fill((240, 242, 246))
    world = pristine.copy()
    fire = FireSystem(rng)
    ctx = ToolContext(world=world, pristine=pristine, particles=ParticleSystem(rng),
                      audio=_Silent(), rng=rng, shake=lambda a: None, size=(W, H), fire=fire)
    tools = {t.id: t for t in build_tools()}
    return ctx, fire, tools


class _Silent:
    def play(self, *a, **k): pass
    def start_loop(self, *a, **k): pass
    def stop_loop(self, *a, **k): pass


def pour(ctx, tools, y=250, x0=200, n=14):
    gas = tools["gasoline"]
    gas.press(ctx, (x0, y))
    for i in range(1, n):
        gas.hold(ctx, (x0 + i * 8, y), (x0 + (i - 1) * 8, y), DT)
    gas.release(ctx, (x0 + (n - 1) * 8, y))


def pixels(surf):
    return pygame.image.tobytes(surf, "RGB")


def main() -> int:
    # Pouring lays down wet fuel and, on its own, damages nothing.
    ctx, fire, tools = fresh()
    before = pixels(ctx.world)
    pour(ctx, tools)
    check("pouring creates fuel", len(fire) > 0)
    check("all poured fuel starts wet", all(p.state == WET for p in fire.puddles))
    check("pouring alone leaves the screen untouched", pixels(ctx.world) == before)

    # The flamethrower sweeping over it lights it.
    tools["flame"].hold(ctx, (240, 250), (200, 250), DT)
    for _ in range(20):
        fire.update(DT, ctx)
    check("flamethrower ignites gasoline",
          any(p.state == BURNING for p in fire.puddles))

    # It burns for a good while, then leaves a permanent scar.
    burning_frames = 0
    for _ in range(60 * 25):
        fire.update(DT, ctx)
        ctx.particles.update(DT, (W, H))
        if any(p.state == BURNING for p in fire.puddles):
            burning_frames += 1
        elif len(fire) == 0:
            break
    check("fire lasts at least 8 seconds", burning_frames * DT >= 8.0)
    check("the burn leaves a permanent mark", pixels(ctx.world) != before)
    check("fuel is fully consumed", len(fire) == 0)

    # A grenade blast ignites gasoline it lands near.
    ctx, fire, tools = fresh()
    pour(ctx, tools, x0=300)
    tools["grenade"].press(ctx, (320, 250))
    lit = False
    for _ in range(60 * 3):
        tools["grenade"].update(ctx, DT, (320, 250), False)
        fire.update(DT, ctx)
        ctx.particles.update(DT, (W, H))
        lit = lit or any(p.state == BURNING for p in fire.puddles)
    check("a grenade blast ignites gasoline", lit)

    # The washer removes unlit fuel.
    ctx, fire, tools = fresh()
    pour(ctx, tools, x0=250)
    n_before = len(fire)
    tools["wash"].press(ctx, (250, 250))
    tools["wash"].hold(ctx, (360, 250), (250, 250), DT)
    fire.update(DT, ctx)
    check("the washer douses gasoline", len(fire) < n_before)

    # Arrows stuck in the screen catch fire, burn away, and leave a mark. Draw
    # every frame -- the char tint is applied at render time, and a burning
    # arrow whose char strayed out of range used to crash pygame here. Several
    # arrows so their randomised burn times cover the full char range.
    ctx, fire, tools = fresh()
    screen = pygame.display.get_surface()
    before = pixels(ctx.world)
    for i in range(6):
        fire.add_arrow((200 + i * 40, 250), 180 + i * 20, 55 + i * 4, 0.6)
    fire.ignite((320, 250), 200, ctx)
    consumed = False
    for _ in range(60 * 8):
        fire.update(DT, ctx)
        ctx.particles.update(DT, (W, H))
        screen.fill((0, 0, 0))
        fire.draw_ground(screen, (0, 0))
        ctx.particles.draw(screen, (0, 0))
        fire.draw_top(screen, (0, 0))          # renders the burning/falling arrows
        if len(fire.arrows) == 0:
            consumed = True
            break
    check("stuck arrows burn away", consumed)
    check("the burnt arrows leave a scar", pixels(ctx.world) != before)

    # A planted bomb goes off on its own the instant fire reaches it -- no
    # remote -- and while a different tool is notionally in hand.
    ctx, fire, tools = fresh()
    trail_x = [150 + i * 9 for i in range(50)]
    gas = tools["gasoline"]
    gas.press(ctx, (trail_x[0], 250))
    for a, b in zip(trail_x, trail_x[1:]):
        gas.hold(ctx, (b, 250), (a, 250), DT)
    gas.release(ctx, (trail_x[-1], 250))
    fire.add_charge((trail_x[-1], 250))         # bomb at the far end of the slick
    fire.ignite((trail_x[0], 250), 25, ctx)     # light only the near end
    auto = False
    for _ in range(60 * 15):
        fire.update(DT, ctx)
        ctx.particles.update(DT, (W, H))
        if fire.charge_count == 0 and not fire.pending:
            auto = True
            break
    check("fire alone sets off a planted bomb (no remote)", auto)

    pygame.quit()
    print("\nFAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
