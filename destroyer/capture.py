"""Screen capture + Windows window plumbing.

Two jobs:
  * grab a pixel-exact shot of the primary display
  * make our borderless window sit on top of everything, at 0,0
"""

from __future__ import annotations

import sys

import numpy as np
import pygame


def make_dpi_aware() -> None:
    """Opt into per-monitor DPI awareness.

    Without this, Windows lies about the screen size on scaled displays and the
    screenshot ends up a different resolution than our window -> blurry, offset
    illusion. Must run before the display is initialised.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        try:
            # PROCESS_PER_MONITOR_DPI_AWARE
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def grab_screen(monitor: int = 1) -> pygame.Surface:
    """Return a Surface holding a screenshot of `monitor` (1 = primary)."""
    try:
        return _grab_mss(monitor)
    except Exception:
        return _grab_pil()


def _grab_mss(monitor: int) -> pygame.Surface:
    import mss

    with mss.mss() as sct:
        mons = sct.monitors
        idx = monitor if 0 < monitor < len(mons) else 1
        shot = sct.grab(mons[idx])

    # mss hands back BGRA; reorder to RGB without a per-pixel Python loop.
    arr = np.frombuffer(shot.raw, dtype=np.uint8).reshape(shot.height, shot.width, 4)
    rgb = np.ascontiguousarray(arr[:, :, 2::-1])
    return pygame.image.frombuffer(rgb, (shot.width, shot.height), "RGB")


def _grab_pil() -> pygame.Surface:
    from PIL import ImageGrab

    img = ImageGrab.grab().convert("RGB")
    return pygame.image.frombuffer(img.tobytes(), img.size, "RGB")


def load_image(path: str) -> pygame.Surface:
    """Dev helper: use a still image instead of a live capture."""
    return pygame.image.load(path).convert()


def set_always_on_top() -> None:
    """Pin the pygame window above the taskbar so the illusion holds."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = pygame.display.get_wm_info()["window"]
        HWND_TOPMOST = -1
        SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x0002, 0x0001, 0x0010
        ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        )
    except Exception:
        pass
