"""最小 GUI 控件库（纯 pygame 绘制）：Label / Button / Slider / Cycler / Toggle。

所有控件都是保留式对象：持有 rect 与回调，handle_event 返回 True 表示消费了事件。
布局由 panel.py 负责，这里只画单个控件。
"""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

import pygame

# ---------------------------------------------------------------------- 主题
THEME = {
    "panel_bg": (22, 24, 30),
    "section_bg": (28, 31, 39),
    "text": (232, 234, 240),
    "text_dim": (150, 156, 168),
    "accent": (96, 146, 255),
    "btn": (50, 55, 67),
    "btn_hover": (64, 70, 86),
    "btn_down": (38, 42, 52),
    "btn_text": (225, 228, 235),
    "track": (42, 46, 56),
    "thumb": (110, 160, 255),
    "disabled": (90, 94, 104),
}

_font_cache = {}


def get_font(size: int = 16) -> pygame.font.Font:
    """中文字体：微软雅黑 → 系统雅黑 → 默认字体。"""
    key = ("ui", size)
    if key not in _font_cache:
        if not pygame.font.get_init():
            pygame.font.init()
        font = None
        for candidate in (r"C:\Windows\Fonts\msyh.ttc",):
            try:
                font = pygame.font.Font(candidate, size)
                break
            except Exception:
                continue
        if font is None:
            try:
                font = pygame.font.SysFont("microsoftyahei", size)
            except Exception:
                font = pygame.font.Font(None, size)
        _font_cache[key] = font
    return _font_cache[key]


class Widget:
    def __init__(self, rect: pygame.Rect) -> None:
        self.rect = pygame.Rect(rect)
        self.enabled = True
        self.visible = True

    def handle_event(self, event: pygame.event.Event) -> bool:
        return False

    def update(self, dt: float) -> None:  # noqa: B027
        pass

    def draw(self, surface: pygame.Surface) -> None:  # noqa: B027
        raise NotImplementedError


def _text(surface: pygame.Surface, txt: str, topleft: Tuple[int, int],
          color, size: int = 14, right: bool = False) -> None:
    img = get_font(size).render(txt, True, color)
    r = img.get_rect()
    if right:
        r.topright = topleft
    else:
        r.topleft = topleft
    surface.blit(img, r)


class Label(Widget):
    def __init__(self, text: str, rect, size: int = 14,
                 color: Optional[str] = None) -> None:
        super().__init__(rect)
        self.text = text
        self.size = size
        self.color_key = color or "text"

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        _text(surface, self.text, self.rect.topleft,
              THEME[self.color_key], self.size)


class Button(Widget):
    def __init__(self, text: str, rect, callback: Callable[[], None],
                 size: int = 14) -> None:
        super().__init__(rect)
        self.text = text
        self.callback = callback
        self._hover = False
        self._down = False
        self.size = size

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not (self.enabled and self.visible):
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(event.pos)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and \
                event.button == 1 and self.rect.collidepoint(event.pos):
            self._down = True
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was = self._down
            self._down = False
            if was and self.rect.collidepoint(event.pos):
                self.callback()
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        color = THEME["btn"]
        if not self.enabled:
            color = (36, 38, 46)
        elif self._down:
            color = THEME["btn_down"]
        elif self._hover:
            color = THEME["btn_hover"]
        pygame.draw.rect(surface, color, self.rect,
                         border_radius=6)
        txt_color = THEME["btn_text"] if self.enabled else THEME["disabled"]
        img = get_font(self.size).render(self.text, True, txt_color)
        surface.blit(img, img.get_rect(center=self.rect.center))


class Slider(Widget):
    """单行滑块：[标签][轨道+滑块][数值]。拖动实时触发 on_change(float)。"""

    LABEL_W = 88
    VALUE_W = 56

    def __init__(self, label: str, rect, min_val: float, max_val: float,
                 value: float, on_change: Callable[[float], None],
                 fmt: Callable[[float], str] = lambda v: f"{v:.2f}",
                 size: int = 13) -> None:
        super().__init__(rect)
        self.label = label
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.value = float(value)
        self.on_change = on_change
        self.fmt = fmt
        self._dragging = False
        self.size = size
        x = rect.x + self.LABEL_W
        w = rect.w - self.LABEL_W - self.VALUE_W - 8
        self.track_rect = pygame.Rect(x, rect.centery - 3, max(10, w), 6)

    # 值 <-> 滑块位置
    def _frac_to_value(self, frac: float) -> float:
        frac = max(0.0, min(1.0, frac))
        return self.min_val + (self.max_val - self.min_val) * frac

    def set_value(self, v: float, fire: bool = False) -> None:
        v = max(self.min_val, min(self.max_val, float(v)))
        changed = abs(v - self.value) > 1e-9
        self.value = v
        if fire and changed:
            self.on_change(self.value)

    def _apply_from_pos(self, x: int) -> None:
        frac = (x - self.track_rect.x) / max(1, self.track_rect.w)
        self.set_value(self._frac_to_value(frac))
        self.on_change(self.value)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not (self.enabled and self.visible):
            return False
        if event.type not in (pygame.MOUSEBUTTONDOWN,
                              pygame.MOUSEBUTTONUP,
                              pygame.MOUSEMOTION):
            return False
        hit = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and hit:
            self._dragging = True
            self._apply_from_pos(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was = self._dragging
            self._dragging = False
            return was
        if event.type == pygame.MOUSEMOTION and self._dragging:
            self._apply_from_pos(event.pos[0])
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        dim = not self.enabled
        col_txt = THEME["disabled"] if dim else THEME["text_dim"]
        _text(surface, self.label, (self.rect.x, self.rect.centery - 9),
              col_txt, self.size)
        tcol = (30, 32, 40) if dim else THEME["track"]
        pygame.draw.rect(surface, tcol, self.track_rect, border_radius=3)
        frac = ((self.value - self.min_val) /
                max(1e-9, self.max_val - self.min_val))
        frac = max(0.0, min(1.0, frac))
        fill_w = int(self.track_rect.w * frac)
        if fill_w > 1:
            fill_col = (60, 66, 80) if dim else THEME["accent"]
            pygame.draw.rect(surface, fill_col,
                             (self.track_rect.x, self.track_rect.y,
                              fill_w, self.track_rect.h), border_radius=3)
        cx = int(self.track_rect.x + fill_w)
        thumb_col = (60, 66, 80) if dim else THEME["thumb"]
        pygame.draw.circle(surface, thumb_col, (cx, self.track_rect.centery), 7)
        pygame.draw.circle(surface, (18, 20, 26),
                           (cx, self.track_rect.centery), 7, 1)
        _text(surface, self.fmt(self.value),
              (self.rect.right - self.VALUE_W, self.rect.centery - 9),
              col_txt, self.size, right=True)


class Cycler(Widget):
    """单行循环选择器：[标签][◀ 当前值 ▶]。点击箭头切换选项。"""

    ARROW_W = 24
    LABEL_W = 88

    def __init__(self, label: str, rect, options: Sequence[str],
                 index: int = 0,
                 on_change: Optional[Callable[[str], None]] = None,
                 size: int = 13) -> None:
        super().__init__(rect)
        self.label = label
        self.options: List[str] = list(options)
        self.index = index if 0 <= index < len(self.options) else 0
        self.on_change = on_change
        self._left_hover = self._right_hover = False
        self.size = size

    @property
    def value(self) -> Optional[str]:
        return self.options[self.index] if self.options else None

    def set_options(self, options: Sequence[str], keep_value: bool = True) -> None:
        cur = self.value
        self.options = list(options)
        if keep_value and cur in self.options:
            self.index = self.options.index(cur)
        else:
            self.index = 0 if self.options else 0

    def _arrow_rects(self) -> Tuple[pygame.Rect, pygame.Rect]:
        cy = self.rect.centery
        lx = self.rect.x + self.LABEL_W
        vw = self.rect.right - lx - 2 * self.ARROW_W - 8
        left = pygame.Rect(lx, cy - 11, self.ARROW_W, 22)
        right = pygame.Rect(left.right + max(10, vw), cy - 11, self.ARROW_W, 22)
        return left, right

    def _cycle(self, direction: int) -> None:
        n = len(self.options)
        if n == 0:
            return
        self.index = (self.index + direction) % n
        self.on_change(self.value)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not (self.enabled and self.visible) or not self.options:
            return False
        lrect, rrect = self._arrow_rects()
        if event.type == pygame.MOUSEMOTION:
            self._left_hover = lrect.collidepoint(event.pos)
            self._right_hover = rrect.collidepoint(event.pos)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if lrect.collidepoint(event.pos):
                self._cycle(-1)
                return True
            if rrect.collidepoint(event.pos):
                self._cycle(+1)
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        _text(surface, self.label, (self.rect.x, self.rect.centery - 9),
              THEME["text_dim"], self.size)
        lrect, rrect = self._arrow_rects()
        for rect, hovered in ((lrect, self._left_hover),
                              (rrect, self._right_hover)):
            col = THEME["btn"] if not hovered else THEME["btn_hover"]
            pygame.draw.rect(surface, col, rect, border_radius=4)
            arrow = "<" if rect is lrect else ">"
            img = get_font(12).render(arrow, True, THEME["btn_text"])
            surface.blit(img, img.get_rect(center=rect.center))
        mid = pygame.Rect(lrect.right + 2, self.rect.y,
                          rrect.left - lrect.right - 4, self.rect.h)
        val = self.value if self.value is not None else "-"
        img = get_font(self.size).render(val, True, THEME["text"])
        surface.blit(img, img.get_rect(center=mid.center))
