"""Floating toolbar.

Draggable by the grip on the left so it can be moved off whatever you are
trying to destroy. Owns its own hit-testing: the app asks `contains()` before
routing a click to a tool, which keeps UI clicks from punching holes in the
desktop underneath.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from .config import (BAR_MARGIN_BOTTOM, BAR_PAD, BAR_RADIUS, BTN, BTN_GAP,
                     COL_ACCENT, COL_ACCENT_SOFT, COL_BAR, COL_BAR_EDGE,
                     COL_BTN, COL_BTN_HOVER, COL_DANGER, COL_TEXT, COL_TEXT_DIM)

GRIP_W = 16
SEP_W = 13


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
        self.buttons: list[Button] = []
        self.dragging = False
        self.drag_offset = (0, 0)
        self.hover: Button | None = None

        inner = (len(tools) + 2) * BTN + (len(tools) + 1) * BTN_GAP + SEP_W
        width = GRIP_W + inner + BAR_PAD * 2
        height = BTN + BAR_PAD * 2
        self.rect = pygame.Rect(0, 0, width, height)
        self.rect.centerx = self.screen_w // 2
        self.rect.bottom = self.screen_h - BAR_MARGIN_BOTTOM
        self._layout()

    # -- geometry ----------------------------------------------------------
    def _layout(self) -> None:
        self.buttons.clear()
        x = self.rect.x + BAR_PAD + GRIP_W
        y = self.rect.y + BAR_PAD
        for tool in self.tools:
            self.buttons.append(Button(pygame.Rect(x, y, BTN, BTN), "tool", tool,
                                       tool.label, tool.hint))
            x += BTN + BTN_GAP
        x += SEP_W - BTN_GAP
        self.buttons.append(Button(pygame.Rect(x, y, BTN, BTN), "action", "clean",
                                   "Wash desktop", "Restore everything  (R)"))
        x += BTN + BTN_GAP
        self.buttons.append(Button(pygame.Rect(x, y, BTN, BTN), "action", "quit",
                                   "Exit", "Quit  (Esc)"))

    @property
    def grip_rect(self) -> pygame.Rect:
        return pygame.Rect(self.rect.x + 4, self.rect.y + 8, GRIP_W, self.rect.h - 16)

    def contains(self, pos) -> bool:
        return self.rect.collidepoint(pos)

    # -- input -------------------------------------------------------------
    def handle_event(self, event) -> str | None:
        """Returns an action name ("clean"/"quit"/"tool") when a button fires."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
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
            self.rect.x = max(0, min(self.screen_w - self.rect.w,
                                     event.pos[0] - self.drag_offset[0]))
            self.rect.y = max(0, min(self.screen_h - self.rect.h,
                                     event.pos[1] - self.drag_offset[1]))
            self._layout()
        return None

    def tool_at(self, pos):
        for btn in self.buttons:
            if btn.kind == "tool" and btn.rect.collidepoint(pos):
                return btn.value
        return None

    def update_hover(self, pos) -> None:
        self.hover = None
        if not self.rect.collidepoint(pos):
            return
        for btn in self.buttons:
            if btn.rect.collidepoint(pos):
                self.hover = btn
                return

    # -- drawing -----------------------------------------------------------
    def draw(self, surf: pygame.Surface, active_tool) -> None:
        panel = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        body = panel.get_rect()

        for i, alpha in enumerate((26, 20, 14)):
            shadow = body.inflate(i * 4, i * 4)
            shadow.y += 3 + i
            pygame.draw.rect(panel, (0, 0, 0, alpha), shadow, border_radius=BAR_RADIUS + i * 2)
        pygame.draw.rect(panel, COL_BAR, body, border_radius=BAR_RADIUS)
        pygame.draw.rect(panel, COL_BAR_EDGE, body, width=1, border_radius=BAR_RADIUS)

        grip = self.grip_rect.move(-self.rect.x, -self.rect.y)
        for row in range(4):
            for col in range(2):
                pygame.draw.circle(panel, (255, 255, 255, 46),
                                   (grip.centerx - 3 + col * 6, grip.y + 6 + row * 8), 1)

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

        sep_x = self.buttons[len(self.tools)].rect.x - self.rect.x - SEP_W // 2 - BTN_GAP // 2
        pygame.draw.line(panel, (255, 255, 255, 28), (sep_x, 14), (sep_x, self.rect.h - 14), 1)

        surf.blit(panel, self.rect.topleft)
        self._draw_tooltip(surf)

    def _draw_tooltip(self, surf: pygame.Surface) -> None:
        if self.hover is None:
            return
        title = self.hover.label
        sub = self.hover.hint
        t_img = self.font_tip.render(title, True, COL_TEXT)
        s_img = self.font.render(sub, True, COL_TEXT_DIM) if sub else None

        w = max(t_img.get_width(), s_img.get_width() if s_img else 0) + 20
        h = t_img.get_height() + (s_img.get_height() + 3 if s_img else 0) + 12
        box = pygame.Rect(0, 0, w, h)
        box.centerx = self.hover.rect.centerx
        box.bottom = self.rect.y - 10
        box.left = max(6, min(self.screen_w - w - 6, box.left))

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
