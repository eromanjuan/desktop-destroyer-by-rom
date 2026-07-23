"""Floating toolbar with three layouts.

A toggle button in the corner (always visible, even when the bar is hidden)
cycles the weapons between:

    bar     the classic horizontal strip
    grid    a compact menu grid, easier to scan once there are many tools
    hidden  out of the way entirely -- only the toggle remains

The panel is draggable, owns its own hit-testing (so a UI click never punches a
hole in the desktop underneath), and `contains()` also covers the toggle button.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from .config import (BAR_MARGIN_BOTTOM, BAR_PAD, BAR_RADIUS, BTN, BTN_GAP,
                     COL_ACCENT, COL_ACCENT_SOFT, COL_BAR, COL_BAR_EDGE,
                     COL_BTN, COL_BTN_HOVER, COL_DANGER, COL_TEXT, COL_TEXT_DIM)

GRIP_W = 16
SEP_W = 13
GRID_COLS = 4
HEADER_H = 26
TOGGLE = 44
MODES = ("bar", "grid", "hidden")


@dataclass
class Button:
    rect: pygame.Rect
    kind: str          # "tool" | "action"
    value: object      # Tool instance, or action name
    label: str
    hint: str = ""


def load_font(size: int, bold: bool = False) -> pygame.font.Font:
    for name in ("Segoe UI", "Inter", "Arial", "DejaVu Sans"):
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f:
                return f
        except Exception:
            continue
    return pygame.font.Font(None, size + 4)


class Toolbar:
    def __init__(self, tools, screen_size):
        self.tools = tools
        self.screen_w, self.screen_h = screen_size
        self.font = load_font(13)
        self.font_tip = load_font(13, bold=True)
        self.font_hdr = load_font(12, bold=True)
        self.buttons: list[Button] = []
        self.dragging = False
        self.drag_offset = (0, 0)
        self.hover: Button | None = None
        self.hover_toggle = False
        self.mode = "bar"

        self.rect = pygame.Rect(0, 0, 10, 10)
        self.toggle_rect = pygame.Rect(0, 0, TOGGLE, TOGGLE)
        self.toggle_rect.bottomright = (self.screen_w - 18, self.screen_h - 18)
        self._resize()

    @property
    def visible(self) -> bool:
        return self.mode != "hidden"

    # -- geometry ----------------------------------------------------------
    def _resize(self) -> None:
        """Size and centre the panel for the current mode, then lay out buttons."""
        n = len(self.tools) + 2      # tools + wash + exit
        if self.mode == "bar":
            inner = (len(self.tools) + 2) * BTN + (len(self.tools) + 1) * BTN_GAP + SEP_W
            w = GRIP_W + inner + BAR_PAD * 2
            h = BTN + BAR_PAD * 2
        elif self.mode == "grid":
            rows = (n + GRID_COLS - 1) // GRID_COLS
            w = GRID_COLS * BTN + (GRID_COLS - 1) * BTN_GAP + BAR_PAD * 2
            h = HEADER_H + rows * BTN + (rows - 1) * BTN_GAP + BAR_PAD
        else:
            self.buttons.clear()
            return
        self.rect = pygame.Rect(0, 0, w, h)
        self.rect.centerx = self.screen_w // 2
        self.rect.bottom = self.screen_h - BAR_MARGIN_BOTTOM
        self._clamp()
        self._layout()

    def _clamp(self) -> None:
        self.rect.x = max(0, min(self.screen_w - self.rect.w, self.rect.x))
        self.rect.y = max(0, min(self.screen_h - self.rect.h, self.rect.y))

    def _layout(self) -> None:
        self.buttons.clear()
        if self.mode == "hidden":
            return
        entries = [("tool", t, t.label, t.hint) for t in self.tools]
        entries.append(("action", "clean", "Wash desktop", "Restore everything  (R)"))
        entries.append(("action", "quit", "Exit", "Quit  (Esc)"))

        if self.mode == "bar":
            x = self.rect.x + BAR_PAD + GRIP_W
            y = self.rect.y + BAR_PAD
            for i, (kind, val, label, hint) in enumerate(entries):
                if i == len(self.tools):          # gap before the action buttons
                    x += SEP_W - BTN_GAP
                self.buttons.append(Button(pygame.Rect(x, y, BTN, BTN), kind, val, label, hint))
                x += BTN + BTN_GAP
        else:  # grid
            x0 = self.rect.x + BAR_PAD
            y0 = self.rect.y + HEADER_H
            for i, (kind, val, label, hint) in enumerate(entries):
                col, row = i % GRID_COLS, i // GRID_COLS
                rect = pygame.Rect(x0 + col * (BTN + BTN_GAP),
                                   y0 + row * (BTN + BTN_GAP), BTN, BTN)
                self.buttons.append(Button(rect, kind, val, label, hint))

    @property
    def grip_rect(self) -> pygame.Rect:
        if self.mode == "grid":
            return pygame.Rect(self.rect.x, self.rect.y, self.rect.w, HEADER_H)
        return pygame.Rect(self.rect.x + 4, self.rect.y + 8, GRIP_W, self.rect.h - 16)

    def contains(self, pos) -> bool:
        if self.toggle_rect.collidepoint(pos):
            return True
        return self.visible and self.rect.collidepoint(pos)

    # -- modes -------------------------------------------------------------
    def cycle_mode(self) -> None:
        self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
        self.hover = None
        self.dragging = False
        self._resize()

    # -- input -------------------------------------------------------------
    def handle_event(self, event) -> str | None:
        """Returns an action ("clean"/"quit"/"tool"/"grab"/"toggle") when hit."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.toggle_rect.collidepoint(event.pos):
                self.cycle_mode()
                return "toggle"
            if not self.visible:
                return None
            if self.grip_rect.collidepoint(event.pos):
                self.dragging = True
                self.drag_offset = (event.pos[0] - self.rect.x, event.pos[1] - self.rect.y)
                return "grab"
            for btn in self.buttons:
                if btn.rect.collidepoint(event.pos):
                    return btn.kind if btn.kind == "tool" else btn.value

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False

        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.rect.x = event.pos[0] - self.drag_offset[0]
            self.rect.y = event.pos[1] - self.drag_offset[1]
            self._clamp()
            self._layout()
        return None

    def tool_at(self, pos):
        for btn in self.buttons:
            if btn.kind == "tool" and btn.rect.collidepoint(pos):
                return btn.value
        return None

    def update_hover(self, pos) -> None:
        self.hover = None
        self.hover_toggle = self.toggle_rect.collidepoint(pos)
        if not self.visible or not self.rect.collidepoint(pos):
            return
        for btn in self.buttons:
            if btn.rect.collidepoint(pos):
                self.hover = btn
                return

    # -- drawing -----------------------------------------------------------
    def draw(self, surf: pygame.Surface, active_tool) -> None:
        if self.visible:
            self._draw_panel(surf, active_tool)
            self._draw_tooltip(surf)
        self._draw_toggle(surf)
        if self.hover_toggle:
            self._draw_toggle_tip(surf)

    def _draw_toggle_tip(self, surf: pygame.Surface) -> None:
        nxt = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
        names = {"bar": "list", "grid": "grid", "hidden": "hidden"}
        t_img = self.font_tip.render("Weapon menu", True, COL_TEXT)
        s_img = self.font.render(f"{names[self.mode]} → {names[nxt]}   ·   click / Tab",
                                 True, COL_TEXT_DIM)
        w = max(t_img.get_width(), s_img.get_width()) + 20
        h = t_img.get_height() + s_img.get_height() + 15
        box = pygame.Rect(0, 0, w, h)
        box.bottomright = (self.toggle_rect.right, self.toggle_rect.top - 8)
        box.left = max(6, box.left)
        tip = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(tip, (18, 19, 24, 236), tip.get_rect(), border_radius=9)
        pygame.draw.rect(tip, COL_BAR_EDGE, tip.get_rect(), width=1, border_radius=9)
        tip.blit(t_img, ((w - t_img.get_width()) // 2, 6))
        tip.blit(s_img, ((w - s_img.get_width()) // 2, 6 + t_img.get_height() + 3))
        surf.blit(tip, box.topleft)

    def _draw_panel(self, surf, active_tool) -> None:
        panel = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        body = panel.get_rect()

        for i, alpha in enumerate((26, 20, 14)):
            shadow = body.inflate(i * 4, i * 4)
            shadow.y += 3 + i
            pygame.draw.rect(panel, (0, 0, 0, alpha), shadow, border_radius=BAR_RADIUS + i * 2)
        pygame.draw.rect(panel, COL_BAR, body, border_radius=BAR_RADIUS)
        pygame.draw.rect(panel, COL_BAR_EDGE, body, width=1, border_radius=BAR_RADIUS)

        if self.mode == "bar":
            grip = self.grip_rect.move(-self.rect.x, -self.rect.y)
            for row in range(4):
                for col in range(2):
                    pygame.draw.circle(panel, (255, 255, 255, 46),
                                       (grip.centerx - 3 + col * 6, grip.y + 6 + row * 8), 1)
        else:  # grid header with a title and drag dots
            hdr = self.font_hdr.render("WEAPONS", True, COL_TEXT_DIM)
            panel.blit(hdr, (BAR_PAD + 2, 7))
            for col in range(3):
                pygame.draw.circle(panel, (255, 255, 255, 40),
                                   (self.rect.w - BAR_PAD - 6 - col * 7, 13), 1)

        for btn in self.buttons:
            local = btn.rect.move(-self.rect.x, -self.rect.y)
            is_active = btn.kind == "tool" and btn.value is active_tool
            is_hover = self.hover is btn

            if is_active:
                pygame.draw.rect(panel, COL_ACCENT_SOFT, local, border_radius=11)
                pygame.draw.rect(panel, (*COL_ACCENT, 200), local, width=1, border_radius=11)
            elif is_hover:
                pygame.draw.rect(panel, COL_BTN_HOVER, local, border_radius=11)
            else:
                pygame.draw.rect(panel, COL_BTN, local, border_radius=11)

            if btn.kind == "tool":
                tint = COL_TEXT if (is_active or is_hover) else COL_TEXT_DIM
                btn.value.draw_icon(panel, local, tint)
            elif btn.value == "clean":
                self._draw_clean_icon(panel, local, COL_TEXT if is_hover else COL_TEXT_DIM)
            else:
                self._draw_exit_icon(panel, local, COL_DANGER if is_hover else COL_TEXT_DIM)

        if self.mode == "bar":
            sep_x = self.buttons[len(self.tools)].rect.x - self.rect.x - SEP_W // 2 - BTN_GAP // 2
            pygame.draw.line(panel, (255, 255, 255, 28), (sep_x, 14), (sep_x, self.rect.h - 14), 1)

        surf.blit(panel, self.rect.topleft)

    def _draw_toggle(self, surf) -> None:
        r = self.toggle_rect
        chip = pygame.Surface(r.size, pygame.SRCALPHA)
        body = chip.get_rect()
        pygame.draw.rect(chip, (0, 0, 0, 40), body.move(0, 3), border_radius=12)
        # Accent when hidden, so the only thing on screen clearly invites a click.
        fill = (*COL_ACCENT, 235) if self.mode == "hidden" else COL_BAR
        pygame.draw.rect(chip, fill, body, border_radius=12)
        pygame.draw.rect(chip, COL_BAR_EDGE, body, width=1, border_radius=12)

        cx, cy = body.center
        ink = (255, 255, 255) if self.mode == "hidden" else COL_TEXT_DIM
        if self.mode == "bar":              # show a grid glyph (next layout)
            for gx in (-5, 5):
                for gy in (-5, 5):
                    pygame.draw.rect(chip, ink, pygame.Rect(cx + gx - 3, cy + gy - 3, 6, 6),
                                     border_radius=1)
        elif self.mode == "grid":           # show an "eye off" / hide glyph
            pygame.draw.line(chip, ink, (cx - 9, cy), (cx + 9, cy), 2)
            pygame.draw.line(chip, ink, (cx - 7, cy + 5), (cx + 7, cy + 5), 2)
        else:                                # hidden -> show a menu glyph to reopen
            for gy in (-6, 0, 6):
                pygame.draw.line(chip, ink, (cx - 8, cy + gy), (cx + 8, cy + gy), 2)
        surf.blit(chip, r.topleft)

    def _draw_tooltip(self, surf: pygame.Surface) -> None:
        if self.hover is None:
            return
        title = self.hover.label
        if self.hover.kind == "tool" and getattr(self.hover.value, "key", None):
            title = f"{title}   ({pygame.key.name(self.hover.value.key).upper()})"
        sub = self.hover.hint
        t_img = self.font_tip.render(title, True, COL_TEXT)
        s_img = self.font.render(sub, True, COL_TEXT_DIM) if sub else None

        w = max(t_img.get_width(), s_img.get_width() if s_img else 0) + 20
        h = t_img.get_height() + (s_img.get_height() + 3 if s_img else 0) + 12
        box = pygame.Rect(0, 0, w, h)
        box.centerx = self.hover.rect.centerx
        box.bottom = self.rect.y - 10 if self.mode == "bar" else self.hover.rect.top - 8
        box.left = max(6, min(self.screen_w - w - 6, box.left))
        box.top = max(6, box.top)

        tip = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(tip, (18, 19, 24, 232), tip.get_rect(), border_radius=9)
        pygame.draw.rect(tip, COL_BAR_EDGE, tip.get_rect(), width=1, border_radius=9)
        tip.blit(t_img, ((w - t_img.get_width()) // 2, 6))
        if s_img:
            tip.blit(s_img, ((w - s_img.get_width()) // 2, 6 + t_img.get_height() + 3))
        surf.blit(tip, box.topleft)

    @staticmethod
    def _draw_clean_icon(surf, rect, tint):
        cx, cy = rect.center
        pygame.draw.polygon(surf, tint, [(cx, cy - 13), (cx + 9, cy + 2),
                                         (cx, cy + 12), (cx - 9, cy + 2)])
        pygame.draw.circle(surf, (30, 32, 40), (cx - 2, cy + 3), 3)

    @staticmethod
    def _draw_exit_icon(surf, rect, tint):
        cx, cy = rect.center
        pygame.draw.line(surf, tint, (cx - 8, cy - 8), (cx + 8, cy + 8), 3)
        pygame.draw.line(surf, tint, (cx + 8, cy - 8), (cx - 8, cy + 8), 3)
