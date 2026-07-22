"""Audio for Desktop Destroyer.

Asset fallback logic: for every sound name we first look for a real file in
`assets/sounds/<name>.{wav,ogg}`. If the user hasn't dropped one in, we
synthesise the sound from noise + sine bursts with numpy, so the app ships with
zero binary assets and still sounds like something is being destroyed.

Every public method is failure-tolerant: no audio device, no numpy, or a broken
wav all degrade to silence rather than crashing the app.
"""

from __future__ import annotations

import os
import random

import numpy as np
import pygame

SR = 44100
EXTS = (".wav", ".ogg")


# --------------------------------------------------------------------------
# tiny DSP helpers
# --------------------------------------------------------------------------
def _n(seconds: float) -> int:
    return max(1, int(SR * seconds))


def _noise(n: int, rng: random.Random) -> np.ndarray:
    gen = np.random.default_rng(rng.getrandbits(32))
    return gen.uniform(-1.0, 1.0, n).astype(np.float32)


def _env(n: int, attack: float = 0.002, power: float = 2.5) -> np.ndarray:
    """Fast attack, exponential-ish decay."""
    a = min(_n(attack), n)
    e = np.ones(n, np.float32)
    e[:a] = np.linspace(0.0, 1.0, a, dtype=np.float32)
    tail = np.linspace(0.0, 1.0, n - a, dtype=np.float32) if n > a else np.zeros(0, np.float32)
    e[a:] = (1.0 - tail) ** power
    return e


def _sweep(f0: float, f1: float, n: int) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SR
    freq = np.linspace(f0, f1, n, dtype=np.float32)
    phase = np.cumsum(2 * np.pi * freq / SR, dtype=np.float32)
    return np.sin(phase).astype(np.float32)


def _lowpass(x: np.ndarray, alpha: float) -> np.ndarray:
    """One-pole lowpass. alpha near 0 = very dark, near 1 = untouched.

    Implemented as a convolution with the filter's (truncated) exponential
    impulse response, which numpy runs in C instead of a per-sample loop.
    """
    alpha = float(np.clip(alpha, 1e-4, 1.0))
    decay = 1.0 - alpha
    length = 1 if decay <= 0 else min(4000, int(np.ceil(np.log(1e-4) / np.log(decay))) + 1)
    kernel = alpha * decay ** np.arange(length, dtype=np.float32)
    return np.convolve(x, kernel.astype(np.float32))[: x.size].astype(np.float32)


def _norm(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = float(np.max(np.abs(x))) or 1.0
    return (x / m * peak).astype(np.float32)


def _mix(*parts: np.ndarray) -> np.ndarray:
    n = max(p.size for p in parts)
    out = np.zeros(n, np.float32)
    for p in parts:
        out[: p.size] += p
    return out


def _seamless(x: np.ndarray, fade: float = 0.12) -> np.ndarray:
    """Crossfade the tail over the head so the buffer loops without a click."""
    f = min(_n(fade), x.size // 3)
    head, tail = x[:f].copy(), x[-f:].copy()
    ramp = np.linspace(0.0, 1.0, f, dtype=np.float32)
    x = x[:-f]
    x[:f] = head * ramp + tail * (1.0 - ramp)
    return x


# --------------------------------------------------------------------------
# synthesis recipes -- each returns mono float32 in [-1, 1]
# --------------------------------------------------------------------------
def _syn_hammer(rng: random.Random) -> np.ndarray:
    n = _n(0.42)
    thud = _sweep(150, 44, n) * _env(n, 0.001, 3.0) * 0.9
    crunch = _lowpass(_noise(n, rng), 0.25) * _env(n, 0.0005, 6.0) * 1.4
    tink = np.zeros(n, np.float32)
    for _ in range(5):
        off = rng.randint(int(SR * 0.02), int(SR * 0.22))
        ln = _n(rng.uniform(0.04, 0.11))
        if off + ln > n:
            continue
        f = rng.uniform(2100, 5200)
        t = np.arange(ln, dtype=np.float32) / SR
        tink[off : off + ln] += np.sin(2 * np.pi * f * t) * _env(ln, 0.001, 4.0) * rng.uniform(0.1, 0.25)
    return _norm(_mix(thud, crunch, tink))


def _syn_gunshot(rng: random.Random) -> np.ndarray:
    n = _n(0.34)
    raw = _noise(n, rng)
    body = _lowpass(raw, 0.12) * _env(n, 0.0004, 5.0) * 1.6
    crack = (raw - _lowpass(raw, 0.5)) * _env(n, 0.0002, 12.0) * 1.2
    boom = _sweep(90, 38, n) * _env(n, 0.001, 4.0) * 0.7
    return _norm(_mix(body, crack, boom))


def _syn_flame(rng: random.Random) -> np.ndarray:
    n = _n(1.4)
    base = _lowpass(_noise(n, rng), 0.06) * 3.0
    hiss = (_noise(n, rng) - _lowpass(_noise(n, rng), 0.35)) * 0.18
    t = np.arange(n, dtype=np.float32) / SR
    wobble = 0.72 + 0.28 * np.sin(2 * np.pi * 3.1 * t) * np.sin(2 * np.pi * 0.7 * t + 1.0)
    return _seamless(_norm(_mix(base, hiss) * wobble, 0.75))


def _syn_ignite(rng: random.Random) -> np.ndarray:
    n = _n(0.5)
    x = _noise(n, rng)
    swell = np.linspace(0.0, 1.0, n, dtype=np.float32)
    return _norm(_lowpass(x, 0.10) * (swell ** 2) * (1.0 - swell * 0.6) * 3.0, 0.8)


def _syn_paint(rng: random.Random) -> np.ndarray:
    n = _n(0.16)
    return _norm(_lowpass(_noise(n, rng), 0.30) * _env(n, 0.01, 3.0), 0.45)


def _syn_wash(rng: random.Random) -> np.ndarray:
    n = _n(1.1)
    x = _lowpass(_noise(n, rng), 0.18)
    x = x - _lowpass(x, 0.03)          # band-ish -> watery, not rumbly
    t = np.arange(n, dtype=np.float32) / SR
    wobble = 0.6 + 0.4 * np.sin(2 * np.pi * 2.3 * t)
    return _seamless(_norm(x * wobble * 2.0, 0.6))


def _syn_clean(rng: random.Random) -> np.ndarray:
    n = _n(0.75)
    swoosh = _lowpass(_noise(n, rng), 0.22) * _env(n, 0.06, 2.0) * 2.0
    sparkle = np.zeros(n, np.float32)
    for i in range(9):
        off = int(n * (0.25 + 0.07 * i))
        ln = _n(0.09)
        if off + ln > n:
            break
        t = np.arange(ln, dtype=np.float32) / SR
        f = 1400 + 380 * i
        sparkle[off : off + ln] += np.sin(2 * np.pi * f * t) * _env(ln, 0.002, 5.0) * 0.22
    return _norm(_mix(swoosh, sparkle), 0.7)


def _syn_bow(rng: random.Random) -> np.ndarray:
    """Bowstring release: a plucked string -- harmonics decaying at different
    rates, with a noise pluck at the very front."""
    n = _n(0.36)
    t = np.arange(n, dtype=np.float32) / SR
    f0 = rng.uniform(155, 205)
    string = np.zeros(n, np.float32)
    for k, amp in ((1, 1.0), (2, 0.52), (3, 0.3), (4, 0.16), (6, 0.08)):
        string += amp * np.sin(2 * np.pi * f0 * k * t) * np.exp(-t * (10.0 + 3.5 * k))
    pluck = _noise(n, rng) * _env(n, 0.0004, 14.0) * 0.55
    return _norm(_mix(string * 0.9, pluck), 0.75)


def _syn_thunk(rng: random.Random) -> np.ndarray:
    """Arrow burying itself in something solid."""
    n = _n(0.3)
    body = _sweep(215, 68, n) * _env(n, 0.0008, 6.0)
    knock = _lowpass(_noise(n, rng), 0.34) * _env(n, 0.0004, 15.0) * 1.3
    return _norm(_mix(body, knock), 0.8)


def _syn_explode(rng: random.Random) -> np.ndarray:
    """Grenade: sub-bass drop under a filtered blast, with a debris tail."""
    n = _n(1.5)
    sub = _sweep(95, 26, n) * _env(n, 0.003, 2.4) * 1.3
    body = _lowpass(_noise(n, rng), 0.07) * _env(n, 0.001, 2.0) * 2.2
    raw = _noise(n, rng)
    crack = (raw - _lowpass(raw, 0.45)) * _env(n, 0.0003, 10.0)

    # Scattered clatter of debris landing after the blast.
    crackle = np.zeros(n, np.float32)
    for _ in range(70):
        off = rng.randint(_n(0.05), n - 400)
        ln = _n(rng.uniform(0.004, 0.02))
        if off + ln > n:
            continue
        crackle[off:off + ln] += _noise(ln, rng) * _env(ln, 0.0005, 6.0) * rng.uniform(0.05, 0.22)

    return _norm(_mix(sub, body, crack, crackle), 0.95)


def _syn_toss(rng: random.Random) -> np.ndarray:
    """Underarm lob -- air moving, nothing more."""
    n = _n(0.28)
    t = np.linspace(0.0, 1.0, n, dtype=np.float32)
    return _norm(_lowpass(_noise(n, rng), 0.12) * (np.sin(np.pi * t) ** 2) * 2.0, 0.4)


def _syn_slash(rng: random.Random) -> np.ndarray:
    """Katana: air being cut, with a little steel ring behind it."""
    n = _n(0.34)
    t = np.arange(n, dtype=np.float32) / SR
    swish = _noise(n, rng)
    # Sweep the filter open then shut so the noise "whooshes" past.
    bright = swish - _lowpass(swish, 0.5)
    env = (np.sin(np.pi * np.linspace(0, 1, n, dtype=np.float32)) ** 3)
    ring = np.sin(2 * np.pi * rng.uniform(2600, 3400) * t) * np.exp(-t * 26.0) * 0.16
    return _norm(_mix(bright * env * 2.2, _lowpass(swish, 0.22) * env * 0.9, ring), 0.6)


def _syn_rock(rng: random.Random) -> np.ndarray:
    """Rock on glass: a blunt knock plus loose gravel."""
    n = _n(0.42)
    thud = _sweep(180, 52, n) * _env(n, 0.001, 4.5)
    grit = _lowpass(_noise(n, rng), 0.30) * _env(n, 0.0006, 9.0) * 1.5
    gravel = np.zeros(n, np.float32)
    for _ in range(14):
        off = rng.randint(_n(0.02), n - 300)
        ln = _n(rng.uniform(0.004, 0.014))
        if off + ln > n:
            continue
        gravel[off:off + ln] += _noise(ln, rng) * _env(ln, 0.0004, 7.0) * rng.uniform(0.08, 0.3)
    return _norm(_mix(thud, grit, gravel), 0.8)


def _syn_click(rng: random.Random) -> np.ndarray:
    n = _n(0.045)
    t = np.arange(n, dtype=np.float32) / SR
    return _norm(np.sin(2 * np.pi * 880 * t) * _env(n, 0.001, 5.0), 0.35)


# name -> (recipe, variant count, default volume)
RECIPES = {
    "hammer": (_syn_hammer, 3, 0.85),
    "gunshot": (_syn_gunshot, 3, 0.7),
    "flame": (_syn_flame, 1, 0.55),
    "ignite": (_syn_ignite, 2, 0.6),
    "paint": (_syn_paint, 3, 0.5),
    "wash": (_syn_wash, 1, 0.5),
    "clean": (_syn_clean, 1, 0.8),
    "click": (_syn_click, 1, 0.4),
    "bow": (_syn_bow, 3, 0.7),
    "thunk": (_syn_thunk, 3, 0.85),
    "explode": (_syn_explode, 3, 0.95),
    "toss": (_syn_toss, 2, 0.4),
    "slash": (_syn_slash, 3, 0.7),
    "rock": (_syn_rock, 3, 0.8),
}


class Audio:
    """Sound bank with per-name variants, looping channels and hard failsafes."""

    def __init__(self, asset_dir: str, enabled: bool = True, rng: random.Random | None = None):
        self.enabled = enabled
        self.rng = rng or random.Random()
        self.bank: dict[str, list[pygame.mixer.Sound]] = {}
        self.volumes: dict[str, float] = {}
        self.loops: dict[str, pygame.mixer.Channel] = {}
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SR, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(32)
        except Exception:
            self.enabled = False
            return
        self._build(asset_dir)

    # -- construction ------------------------------------------------------
    def _build(self, asset_dir: str) -> None:
        for name, (recipe, variants, vol) in RECIPES.items():
            self.volumes[name] = vol
            loaded = self._from_disk(asset_dir, name)
            if loaded:
                self.bank[name] = loaded
                continue
            try:
                self.bank[name] = [self._to_sound(recipe(self.rng)) for _ in range(variants)]
            except Exception:
                self.bank[name] = []

    def _from_disk(self, asset_dir: str, name: str) -> list[pygame.mixer.Sound]:
        found = []
        for ext in EXTS:
            path = os.path.join(asset_dir, name + ext)
            if os.path.isfile(path):
                try:
                    found.append(pygame.mixer.Sound(path))
                except Exception:
                    pass
        return found

    @staticmethod
    def _to_sound(mono: np.ndarray) -> pygame.mixer.Sound:
        clipped = np.clip(mono, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype(np.int16)
        stereo = np.ascontiguousarray(np.column_stack([pcm, pcm]))
        return pygame.sndarray.make_sound(stereo)

    # -- playback ----------------------------------------------------------
    def play(self, name: str, volume: float = 1.0, pitch_jitter: bool = True) -> None:
        if not self.enabled:
            return
        pool = self.bank.get(name)
        if not pool:
            return
        snd = self.rng.choice(pool)
        try:
            vol = self.volumes.get(name, 1.0) * volume
            if pitch_jitter:
                vol *= self.rng.uniform(0.85, 1.0)
            snd.set_volume(max(0.0, min(1.0, vol)))
            snd.play()
        except Exception:
            pass

    def start_loop(self, name: str, volume: float = 1.0) -> None:
        if not self.enabled or name in self.loops:
            return
        pool = self.bank.get(name)
        if not pool:
            return
        try:
            ch = pygame.mixer.find_channel(True)
            if ch is None:
                return
            snd = pool[0]
            snd.set_volume(max(0.0, min(1.0, self.volumes.get(name, 1.0) * volume)))
            ch.play(snd, loops=-1, fade_ms=60)
            self.loops[name] = ch
        except Exception:
            pass

    def stop_loop(self, name: str) -> None:
        ch = self.loops.pop(name, None)
        if ch is None:
            return
        try:
            ch.fadeout(120)
        except Exception:
            pass

    def stop_all(self) -> None:
        for name in list(self.loops):
            self.stop_loop(name)
        if self.enabled:
            try:
                pygame.mixer.stop()
            except Exception:
                pass
