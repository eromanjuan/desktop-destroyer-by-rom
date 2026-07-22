"""Input-routing regression test.

Drives the real App through synthetic pygame events under the dummy video
driver. Covers the logic that is easy to break and invisible in a screenshot:
UI clicks must never punch holes in the desktop, and a wash must restore the
capture byte-for-byte.

    python tests/test_input.py      -> exits 0 on success, 1 on failure
"""

import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from destroyer.app import App  # noqa: E402

failures: list[str] = []


def check(label: str, condition: bool) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    if not condition:
        failures.append(label)


def main() -> int:
    app = App(windowed=True, audio_enabled=False, seed=3)
    bar = app.toolbar

    def send(**kw):
        pygame.event.post(pygame.event.Event(kw.pop("type"), **kw))
        app.handle_events()

    def button(value):
        # Dragging the bar rebuilds its button list -- always re-fetch.
        return [b for b in bar.buttons if b.value == value][0]

    def pixels(surface):
        return pygame.image.tobytes(surface, "RGB")

    # A toolbar click selects a tool and must not damage the desktop under it.
    tool_btn = bar.buttons[2]
    before = pixels(app.world)
    send(type=pygame.MOUSEBUTTONDOWN, button=1, pos=tool_btn.rect.center)
    send(type=pygame.MOUSEBUTTONUP, button=1, pos=tool_btn.rect.center)
    check("toolbar click selects tool", app.tool is tool_btn.value)
    check("toolbar click leaves desktop intact", pixels(app.world) == before)
    check("toolbar click does not start drawing", app.drawing is False)

    send(type=pygame.KEYDOWN, key=pygame.K_1, mod=0, unicode="1", scancode=0)
    check("hotkey 1 selects hammer", app.tool.id == "hammer")

    # Dragging the grip repositions the bar, still without damaging anything.
    before = pixels(app.world)
    origin = bar.rect.topleft
    send(type=pygame.MOUSEBUTTONDOWN, button=1, pos=bar.grip_rect.center)
    send(type=pygame.MOUSEMOTION,
         pos=(bar.grip_rect.centerx + 60, bar.grip_rect.centery - 40),
         rel=(60, -40), buttons=(1, 0, 0))
    send(type=pygame.MOUSEBUTTONUP, button=1, pos=(0, 0))
    check("grip drag moves toolbar", bar.rect.topleft != origin)
    check("grip drag leaves desktop intact", pixels(app.world) == before)

    # Clicking open desktop, on the other hand, must damage it.
    before = pixels(app.world)
    send(type=pygame.MOUSEBUTTONDOWN, button=1, pos=(300, 200))
    check("desktop click starts drawing", app.drawing is True)
    check("desktop click damages world", pixels(app.world) != before)
    send(type=pygame.MOUSEBUTTONUP, button=1, pos=(300, 200))
    check("mouse up stops drawing", app.drawing is False)

    # Remote bomb: left-click plants, right-click sets the whole field off.
    bomb = [t for t in app.tools if t.id == "bomb"][0]
    app.select(bomb)
    for spot in ((200, 150), (400, 250), (600, 340)):
        send(type=pygame.MOUSEBUTTONDOWN, button=1, pos=spot)
        send(type=pygame.MOUSEBUTTONUP, button=1, pos=spot)
    check("left-click plants charges", len(bomb.charges) == 3)

    # A right-click on the toolbar is the UI's, not the tool's.
    send(type=pygame.MOUSEBUTTONDOWN, button=3, pos=bar.rect.center)
    check("right-click on toolbar is ignored", len(bomb.charges) == 3)

    before = pixels(app.world)
    send(type=pygame.MOUSEBUTTONDOWN, button=3, pos=(700, 420))
    check("right-click triggers every charge",
          len(bomb.charges) == 0 and len(bomb.pending) == 3)
    check("right-click never starts a drag", app.drawing is False)
    for _ in range(120):
        app.update(1 / 60)
    check("chain detonates and craters the desktop", pixels(app.world) != before)
    check("chain fully drains", not bomb.pending)

    send(type=pygame.MOUSEBUTTONDOWN, button=1, pos=button("clean").rect.center)
    send(type=pygame.MOUSEBUTTONUP, button=1, pos=button("clean").rect.center)
    for _ in range(90):
        app.update(1 / 60)
    check("wash sweep finishes", app.sweep_x is None)
    check("wash restores pristine desktop", pixels(app.world) == pixels(app.pristine))

    # Spacebar writes a PNG of the damage; Backspace washes like R.
    import glob

    shots = os.path.join(os.path.expanduser("~"), "Pictures", "Desktop Destroyer")
    before_count = len(glob.glob(os.path.join(shots, "destroyed-*.png")))
    send(type=pygame.MOUSEBUTTONDOWN, button=1, pos=(320, 210))
    send(type=pygame.MOUSEBUTTONUP, button=1, pos=(320, 210))
    send(type=pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ", scancode=0)
    saved = sorted(glob.glob(os.path.join(shots, "destroyed-*.png")))
    check("spacebar saves a screenshot", len(saved) == before_count + 1)
    if saved:
        img = pygame.image.load(saved[-1])
        check("screenshot matches the desktop size", img.get_size() == app.size)
        os.remove(saved[-1])                      # don't litter the real folder
    check("spacebar shows a confirmation", app.toast_timer > 0)

    send(type=pygame.KEYDOWN, key=pygame.K_BACKSPACE, mod=0, unicode="", scancode=0)
    check("backspace starts a wash", app.sweep_x is not None)
    for _ in range(90):
        app.update(1 / 60)
    check("backspace wash restores the desktop", pixels(app.world) == pixels(app.pristine))

    send(type=pygame.MOUSEBUTTONDOWN, button=1, pos=button("quit").rect.center)
    check("exit button quits", app.running is False)
    app.running = True
    send(type=pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0)
    check("escape quits", app.running is False)

    app.shutdown()
    print("\nFAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
