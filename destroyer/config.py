"""Tunable constants for Desktop Destroyer.

Everything a designer would want to tweak lives here so tools stay readable.
"""

FPS = 120

# --- particles -------------------------------------------------------------
MAX_PARTICLES = 1600

# --- screen shake ----------------------------------------------------------
SHAKE_DECAY = 7.0          # how fast the trauma value falls off, per second
SHAKE_MAX = 22.0           # hard cap on pixel offset

# --- toolbar ---------------------------------------------------------------
BAR_HEIGHT = 66
BTN = 48
BTN_GAP = 6
BAR_PAD = 9
BAR_MARGIN_BOTTOM = 26
BAR_RADIUS = 14

COL_BAR = (22, 24, 30, 214)
COL_BAR_EDGE = (255, 255, 255, 26)
COL_BTN = (255, 255, 255, 16)
COL_BTN_HOVER = (255, 255, 255, 40)
COL_ACCENT = (255, 96, 48)
COL_ACCENT_SOFT = (255, 96, 48, 58)
COL_TEXT = (232, 234, 240)
COL_TEXT_DIM = (150, 155, 168)
COL_DANGER = (255, 92, 92)

# --- hint overlay ----------------------------------------------------------
HINT_TEXT = "ESC quit  ·  letter keys pick weapons  ·  TAB toolbar mode  ·  R wash  ·  SPACE screenshot"
HINT_HOLD = 3.2            # seconds fully visible
HINT_FADE = 1.4            # seconds to fade out
