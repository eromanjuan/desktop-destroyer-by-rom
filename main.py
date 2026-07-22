"""Desktop Destroyer -- entry point.

    python main.py                 fullscreen, live screen capture
    python main.py --windowed      1280x760 window (safe for development)
    python main.py --image shot.png    use a still image instead of a capture
    python main.py --selftest      headless smoke test, no window
"""

from __future__ import annotations

import argparse
import os
import sys


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Smash, shoot, burn and paint your desktop.")
    p.add_argument("--windowed", action="store_true",
                   help="run in a window instead of borderless fullscreen")
    p.add_argument("--image", metavar="PATH",
                   help="destroy a still image instead of a live screen capture")
    p.add_argument("--monitor", type=int, default=1,
                   help="which display to capture (1 = primary, default: 1)")
    p.add_argument("--no-audio", action="store_true", help="disable all sound")
    p.add_argument("--selftest", action="store_true",
                   help="exercise every tool headlessly and exit")
    return p.parse_args(argv)


def _report_crash(exc: BaseException) -> None:
    """Frozen builds have no console, so a crash would otherwise be silent.

    Write the traceback next to the executable and tell the user where it went.
    """
    import traceback

    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    folder = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False)
                                             else __file__))
    log = os.path.join(folder, "Desktop Destroyer crash.log")
    try:
        with open(log, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError:
        log = "(could not be written)"

    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None,
                f"Desktop Destroyer hit an error and had to close.\n\n"
                f"{type(exc).__name__}: {exc}\n\nDetails saved to:\n{log}",
                "Desktop Destroyer by Rom", 0x10)
        except Exception:
            pass
    else:
        print(text, file=sys.stderr)


def main(argv=None) -> int:
    args = parse_args(argv)

    from destroyer.app import App, selftest

    if args.selftest:
        return selftest()

    try:
        App(
            windowed=args.windowed,
            image=args.image,
            monitor=args.monitor,
            audio_enabled=not args.no_audio,
        ).run()
    except Exception as exc:            # noqa: BLE001 -- last line of defence
        _report_crash(exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
