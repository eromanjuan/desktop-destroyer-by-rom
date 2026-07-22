"""Build a standalone Desktop Destroyer executable.

    python build.py              generate the icon, then build the .exe
    python build.py --icon-only  just regenerate assets/icon.ico

The result is a single self-contained file in dist/ that needs no Python and no
installer -- copy it anywhere and double-click it.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(HERE, "assets", "icon.ico")
APP_NAME = "Desktop Destroyer by Rom"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


# ---------------------------------------------------------------------------
# icon
# ---------------------------------------------------------------------------
def draw_icon(size: int = 512):
    """Draw the app icon: a hammer mid-swing over cracked glass.

    The hammer is the tool the app opens with, so it's the natural mark. Drawn
    with pygame rather than shipped as a binary, so it stays editable in code.
    """
    import math

    import pygame

    if not pygame.get_init():
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((1, 1))

    s = pygame.Surface((size, size), pygame.SRCALPHA)
    k = size / 512.0            # everything below is authored at 512px

    def p(*vals):
        return tuple(v * k for v in vals) if len(vals) > 1 else vals[0] * k

    # Rounded plate with a warm-to-dark vertical wash.
    plate = pygame.Surface((size, size), pygame.SRCALPHA)
    for y in range(size):
        t = y / size
        plate.fill((int(38 - 14 * t), int(40 - 15 * t), int(52 - 20 * t)),
                   pygame.Rect(0, y, size, 1))
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=int(p(112)))
    plate.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(plate, (0, 0))

    # Impact glow. Many faint concentric steps rather than three fat ones --
    # three leave a visible hard rim that reads as a muddy brown disc.
    cx, cy = p(300), p(304)
    glow = pygame.Surface((size, size), pygame.SRCALPHA)
    for i in range(34, 0, -1):
        radius = int(p(20) + (p(212) - p(20)) * (i / 34.0))
        pygame.draw.circle(glow, (255, 116, 40, 7), (int(cx), int(cy)), radius)
    s.blit(glow, (0, 0))

    # Cracks radiating from the impact point. Bright, few and thick, so they
    # survive being squashed down to a 16px taskbar icon.
    for i in range(7):
        ang = i * (math.tau / 7) + 0.34
        pts, x, y, a = [(cx, cy)], cx, cy, ang
        for step in range(4):
            a += (0.24 if step % 2 else -0.2)
            x += math.cos(a) * p(58)
            y += math.sin(a) * p(58)
            pts.append((x, y))
        pygame.draw.lines(s, (18, 14, 12, 220), False,
                          [(px + p(3), py + p(3)) for px, py in pts], max(1, int(p(11))))
        pygame.draw.lines(s, (255, 206, 150), False, pts, max(1, int(p(5))))

    # Hammer: one bold diagonal, sized to dominate the plate. At small sizes an
    # icon gets exactly one readable shape, and this is it.
    hx, hy = p(150), p(430)          # grip
    tx, ty = p(310), p(212)          # neck
    pygame.draw.line(s, (44, 27, 15), (hx, hy), (tx, ty), int(p(52)))
    pygame.draw.line(s, (132, 86, 46), (hx, hy), (tx, ty), int(p(38)))
    pygame.draw.line(s, (186, 132, 78), (hx - p(7), hy - p(7)), (tx - p(7), ty - p(7)),
                     int(p(11)))

    head = [(p(250), p(186)), (p(404), p(106)), (p(462), p(200)), (p(308), p(280))]
    claw = [(p(250), p(186)), (p(308), p(280)), (p(232), p(298)), (p(206), p(232))]
    for poly in (claw, head):
        pygame.draw.polygon(s, (78, 84, 98), poly)
        pygame.draw.polygon(s, (20, 22, 28), poly, int(p(12)))
    pygame.draw.polygon(s, (176, 186, 204), [
        (p(266), p(190)), (p(398), p(122)), (p(418), p(154)), (p(286), p(222)),
    ])
    return s


def write_icon() -> str:
    import pygame
    from PIL import Image

    surf = draw_icon(512)
    raw = pygame.image.tobytes(surf, "RGBA")
    img = Image.frombytes("RGBA", surf.get_size(), raw)

    os.makedirs(os.path.dirname(ICON), exist_ok=True)
    img.save(ICON, format="ICO", sizes=[(n, n) for n in ICON_SIZES])
    png = os.path.join(HERE, "docs", "icon.png")
    os.makedirs(os.path.dirname(png), exist_ok=True)
    img.save(png)
    print(f"icon  -> {ICON}  ({', '.join(str(n) for n in ICON_SIZES)})")
    return ICON


# ---------------------------------------------------------------------------
# executable
# ---------------------------------------------------------------------------
def build_exe(clean: bool = True) -> int:
    if clean:
        for folder in ("build", "dist"):
            path = os.path.join(HERE, folder)
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                     # a single .exe, nothing to install
        "--noconsole",                   # no black console window behind the game
        "--name", APP_NAME,
        "--icon", ICON,
        "--collect-submodules", "destroyer",
        # Trim the parts of numpy/PIL a game like this never touches.
        "--exclude-module", "tkinter",
        "--exclude-module", "unittest",
        "--exclude-module", "pydoc",
        "--exclude-module", "numpy.f2py",
        "--exclude-module", "PIL.ImageQt",
        "--noconfirm",
        os.path.join(HERE, "main.py"),
    ]
    print("running:", " ".join(cmd[:8]), "...")
    result = subprocess.run(cmd, cwd=HERE)
    if result.returncode != 0:
        return result.returncode

    exe = os.path.join(HERE, "dist", APP_NAME + ".exe")
    if os.path.isfile(exe):
        mb = os.path.getsize(exe) / (1024 * 1024)
        print(f"\nbuilt -> {exe}  ({mb:.1f} MB)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the standalone executable.")
    ap.add_argument("--icon-only", action="store_true", help="just regenerate the icon")
    ap.add_argument("--no-clean", action="store_true", help="keep previous build output")
    args = ap.parse_args()

    write_icon()
    if args.icon_only:
        return 0
    return build_exe(clean=not args.no_clean)


if __name__ == "__main__":
    sys.exit(main())
