# Sound overrides

This folder is empty by design. Every sound the app uses is synthesised at
startup in `destroyer/audio.py`, so the project needs no binary assets.

Drop a `.wav` or `.ogg` here to override one. Files found on disk take priority
over the generated version:

| File | Used for | Notes |
|---|---|---|
| `hammer.wav` | Hammer impact | |
| `slash.wav` | Katana cut | |
| `gunshot.wav` | Shotgun blast | |
| `bow.wav` | Bowstring release | |
| `thunk.wav` | Arrow landing | |
| `rock.wav` | Rock impact | |
| `toss.wav` | Rock or grenade being thrown | |
| `explode.wav` | Grenade / remote bomb blast | chained blasts play it many times over |
| `flame.wav` | Flamethrower | **looped** — must be seamless |
| `ignite.wav` | Flame start-up whoosh | |
| `paint.wav` | Brush stroke | played repeatedly, keep it short and quiet |
| `wash.wav` | Scrubbing | **looped** — must be seamless |
| `clean.wav` | Full desktop wipe | |
| `click.wav` | Toolbar button | |

If a file fails to load, the app falls back to the synthesised sound rather than
failing to start.
