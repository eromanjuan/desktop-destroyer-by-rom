"""Application shell: window, layers, input routing, render loop.

Layer model
-----------
`pristine`  the untouched capture. Read-only. The washer restores from it.
`world`     a mutable copy that every tool draws damage into. Opaque, so the
            per-frame cost is one fast blit regardless of how wrecked it is.
particles   transient, redrawn from scratch each frame on top of `world`.
toolbar     drawn last and deliberately never shaken, so the UI stays readable.
"""

from __future__ import annotations

import os
import random
import sys

import pygame

from . import capture, decals
from . import APP_NAME
from .audio import Audio
from .config import (FPS, HINT_FADE, HINT_HOLD, HINT_TEXT, SHAKE_DECAY,
                     SHAKE_MAX)
from .particles import ParticleSystem
from .toolbar import Toolbar, load_font
from .tools import ToolContext, build_tools

def _asset_root() -> str:
    """Where to look for optional sound overrides.

    Running from source that's the project folder. Frozen into an .exe it's the
    folder holding the .exe -- NOT PyInstaller's temp extraction dir -- so a user
    can drop their own wavs next to the executable without rebuilding anything.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ASSET_SOUNDS = os.path.join(_asset_root(), "assets", "sounds")

SWEEP_DURATION = 0.55


class App:
    def __init__(self, windowed=False, image=None, monitor=1,
                 audio_enabled=True, seed=None):
        self.rng = random.Random(seed)

        capture.make_dpi_aware()
        pygame.init()

        # Grab the screen BEFORE our own window exists, or we photograph ourselves.
        shot = capture.load_image(image) if image and os.path.isfile(image) \
            else capture.grab_screen(monitor)

        size = shot.get_size()
        if windowed:
            size = (min(1280, size[0]), min(760, size[1]))
            flags = 0
        else:
            os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "0,0")
            flags = pygame.NOFRAME

        try:
            self.screen = pygame.display.set_mode(size, flags, vsync=1)
        except pygame.error:
            self.screen = pygame.display.set_mode(size, flags)
        pygame.display.set_caption(APP_NAME)
        self.size = self.screen.get_size()

        if shot.get_size() != self.size:
            shot = pygame.transform.smoothscale(shot, self.size)
        self.pristine = shot.convert()
        self.world = self.pristine.copy()

        if not windowed:
            capture.set_always_on_top()
        pygame.mouse.set_visible(False)

        self.audio = Audio(ASSET_SOUNDS, enabled=audio_enabled, rng=self.rng)
        self.particles = ParticleSystem(self.rng)
        self.tools = build_tools()
        self.tool = self.tools[0]
        self.toolbar = Toolbar(self.tools, self.size)
        self.font_hint = load_font(15, bold=True)

        self.ctx = ToolContext(
            world=self.world, pristine=self.pristine, particles=self.particles,
            audio=self.audio, rng=self.rng, shake=self.add_shake, size=self.size,
        )

        self.clock = pygame.time.Clock()
        self.running = True
        self.trauma = 0.0
        self.drawing = False
        self.prev_mouse = pygame.mouse.get_pos()
        self.hint_timer = 0.0
        self.sweep_x = None

    # -- effects -----------------------------------------------------------
    def add_shake(self, amount: float) -> None:
        self.trauma = min(1.0, self.trauma + amount)

    def start_sweep(self) -> None:
        """Squeegee the whole desktop clean, left to right."""
        if self.sweep_x is not None:
            return
        self.sweep_x = 0.0
        self.audio.play("clean")

    def _update_sweep(self, dt: float) -> None:
        if self.sweep_x is None:
            return
        w, h = self.size
        speed = w / SWEEP_DURATION
        x0 = self.sweep_x
        x1 = min(float(w), x0 + speed * dt)
        band = pygame.Rect(int(x0), 0, max(1, int(x1 - x0) + 1), h)
        band = band.clip(self.world.get_rect())
        if band.width > 0:
            self.world.blit(self.pristine, band.topleft, area=band)
        for _ in range(5):
            self.particles.water((x1, self.rng.uniform(0, h)), count=2)
        self.sweep_x = None if x1 >= w else x1

    # -- input -------------------------------------------------------------
    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    self.running = False
                elif event.key == pygame.K_r:
                    self.start_sweep()
                else:
                    for tool in self.tools:
                        if tool.key == event.key:
                            self.select(tool)

            elif event.type == pygame.MOUSEWHEEL:
                step = -1 if event.y > 0 else 1
                self.select(self.tools[(self.tools.index(self.tool) + step) % len(self.tools)])

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                action = self.toolbar.handle_event(event)
                if action == "quit":
                    self.running = False
                elif action == "clean":
                    self.start_sweep()
                    self.audio.play("click")
                elif action == "tool":
                    picked = self.toolbar.tool_at(event.pos)
                    if picked:
                        self.select(picked)
                        self.audio.play("click")
                elif action != "grab" and not self.toolbar.contains(event.pos):
                    self.drawing = True
                    self.prev_mouse = event.pos
                    self.tool.press(self.ctx, event.pos)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                # Secondary action. Never starts a drag, and the toolbar swallows it.
                if not self.toolbar.contains(event.pos):
                    self.tool.alt_press(self.ctx, event.pos)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.toolbar.handle_event(event)
                if self.drawing:
                    self.drawing = False
                    self.tool.release(self.ctx, event.pos)

            elif event.type == pygame.MOUSEMOTION:
                self.toolbar.handle_event(event)

    def select(self, tool) -> None:
        if tool is self.tool:
            return
        self.tool.deactivate(self.ctx)
        self.drawing = False
        self.tool = tool

    # -- frame -------------------------------------------------------------
    def update(self, dt: float) -> None:
        pos = pygame.mouse.get_pos()
        self.toolbar.update_hover(pos)
        self.tool.update(self.ctx, dt, pos, self.drawing)
        if self.drawing:
            self.tool.hold(self.ctx, pos, self.prev_mouse, dt)
        self.prev_mouse = pos

        self._update_sweep(dt)
        self.particles.update(dt, self.size)
        self.trauma = max(0.0, self.trauma - SHAKE_DECAY * dt * max(0.35, self.trauma))
        self.hint_timer += dt

    def draw(self) -> None:
        offset = (0.0, 0.0)
        if self.trauma > 0.005:
            mag = SHAKE_MAX * (self.trauma ** 2)
            offset = (self.rng.uniform(-mag, mag), self.rng.uniform(-mag, mag))
            self.screen.fill((0, 0, 0))

        self.screen.blit(self.world, offset)
        self.particles.draw(self.screen, offset)
        self.tool.draw_overlay(self.screen, offset)

        if self.sweep_x is not None:
            self._draw_foam(int(self.sweep_x))

        self.toolbar.draw(self.screen, self.tool)
        self._draw_hint()

        pos = pygame.mouse.get_pos()
        if not self.toolbar.contains(pos):
            self.tool.draw_cursor(self.screen, pos)
        else:
            pygame.draw.circle(self.screen, (255, 255, 255), pos, 5)
            pygame.draw.circle(self.screen, (20, 20, 24), pos, 5, 1)

        pygame.display.flip()

    def _draw_foam(self, x: int) -> None:
        h = self.size[1]
        foam = pygame.Surface((26, h), pygame.SRCALPHA)
        for i in range(26):
            alpha = int(150 * (1.0 - abs(i - 13) / 13.0))
            pygame.draw.line(foam, (235, 248, 255, alpha), (i, 0), (i, h))
        self.screen.blit(foam, (x - 13, 0))

    def _draw_hint(self) -> None:
        if self.hint_timer > HINT_HOLD + HINT_FADE:
            return
        fade = 1.0
        if self.hint_timer > HINT_HOLD:
            fade = 1.0 - (self.hint_timer - HINT_HOLD) / HINT_FADE
        img = self.font_hint.render(HINT_TEXT, True, (245, 246, 250))
        box = img.get_rect()
        box.inflate_ip(26, 16)
        box.centerx = self.size[0] // 2
        box.top = 26

        panel = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (18, 19, 24, int(215 * fade)), panel.get_rect(), border_radius=10)
        pygame.draw.rect(panel, (255, 255, 255, int(30 * fade)), panel.get_rect(),
                         width=1, border_radius=10)
        img.set_alpha(int(255 * fade))
        panel.blit(img, ((box.w - img.get_width()) // 2, (box.h - img.get_height()) // 2))
        self.screen.blit(panel, box.topleft)

    # -- lifecycle ---------------------------------------------------------
    def run(self) -> None:
        try:
            while self.running:
                dt = min(0.05, self.clock.tick(FPS) / 1000.0)
                self.handle_events()
                self.update(dt)
                self.draw()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        for tool in self.tools:
            tool.deactivate(self.ctx)
        self.audio.stop_all()
        pygame.quit()


def selftest(frames: int = 40) -> int:
    """Headless smoke test: drive every tool and assert nothing explodes."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"

    app = App(windowed=True, image=None, audio_enabled=False, seed=7)
    w, h = app.size
    failed = []
    for tool in app.tools:
        app.select(tool)
        app.particles.clear()          # so `peak` measures this tool alone
        pos = (w // 2, h // 2)
        before = pygame.image.tobytes(app.world, "RGB")
        peak = 0

        tool.press(app.ctx, pos)
        for i in range(frames):
            nxt = (pos[0] + 7, pos[1] + (3 if i % 2 else -3))
            tool.update(app.ctx, 1 / 60, nxt, True)
            tool.hold(app.ctx, nxt, pos, 1 / 60)
            app.particles.update(1 / 60, app.size)
            app.draw()
            peak = max(peak, len(app.particles))
            pos = nxt
        tool.release(app.ctx, pos)
        # Secondary action -- a no-op for most tools, but it is the only thing
        # that makes the remote bomb do anything at all.
        tool.alt_press(app.ctx, pos)

        # Tools with deferred effects only land their damage some time after
        # release -- keep ticking long enough to cover the slowest of them
        # (the grenade's flight plus its full fuse) so that path really runs.
        for _ in range(140):
            tool.update(app.ctx, 1 / 60, pos, False)
            app.particles.update(1 / 60, app.size)
            app.draw()
            peak = max(peak, len(app.particles))

        # Peak, not final: by now most particles have expired, so a final count
        # of zero would hide a tool that never emitted anything at all.
        marked = pygame.image.tobytes(app.world, "RGB") != before
        ok = marked and peak > 0
        if not ok:
            failed.append(tool.label)
        print(f"  {'ok ' if ok else 'FAIL'}  {tool.label:<14} "
              f"peak_particles={peak:<5} damaged_world={marked}")

    if failed:
        print("FAILED:", ", ".join(failed))
        app.shutdown()
        return 1

    app.start_sweep()
    for _ in range(60):
        app.update(1 / 60)
        app.draw()

    decals.soft_restore(app.world, app.pristine, (w // 2, h // 2), 40)
    app.shutdown()
    print("selftest passed")
    return 0
