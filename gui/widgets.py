"""最小 GUI 控件库（纯 pygame 绘制）：Label / Button / Slider / Cycler / Toggle。

所有控件都是保留式对象：持有 rect 与回调，handle_event 返回 True 表示消费了事件。
布局由 panel.py 负责，这里只画单个控件。
"""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

import pygame

from kokoro_engine.assets import BG_ROOT, FG_ROOT

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


class ResourceBrowser(Widget):
    """模态资源浏览器：文件夹=分类可进入，图片条目带缩略图，点击即选用。"""

    TITLE_H = 34
    ROW_H = 62
    THUMB = (52, 52)
    BTN_W = 44

    def __init__(self, rect, assets, on_select) -> None:
        super().__init__(rect)
        self.assets = assets
        self.on_select = on_select          # callable(target: str, key: str)
        self.target: Optional[str] = None   # "bg" | "img"；None=未打开
        self.root_dir = ""                  # 分类根（导航不越出）
        self.rel_dir = ""
        self.scroll_y = 0
        self._dirs: List[str] = []
        self._images: List[str] = []
        self.visible = False                # 弹层默认关闭
        self.btn_refresh = pygame.Rect(0, 0, self.BTN_W - 6,
                                       self.TITLE_H - 10)
        self.btn_close = pygame.Rect(0, 0, self.BTN_W - 6,
                                     self.TITLE_H - 10)
        self._overlay_cache = {}

    @property
    def modal_open(self) -> bool:
        return self.visible

    # ------------------------------------------------------------------ 打开
    def open(self, target: str) -> None:
        self.target = target
        self.visible = True
        self.root_dir = BG_ROOT if target == "bg" else FG_ROOT
        self.rel_dir = self.root_dir
        self.refresh_listing()

    def close(self) -> None:
        self.visible = False
        self.target = None

    def refresh_listing(self) -> None:
        self.assets.rescan()
        self._dirs, self._images = self.assets.list_dir(self.rel_dir)
        self.clamp_scroll()

    def _entries(self) -> List[tuple]:
        """(kind, value)：kind ∈ up/dir/img。分类根下不给 up。"""
        out = []
        if self.rel_dir and self.rel_dir != self.root_dir:
            out.append(("up", None))
        out.extend(("dir", d) for d in self._dirs)
        out.extend(("img", k) for k in self._images)
        return out

    def _viewport(self) -> pygame.Rect:
        return pygame.Rect(self.rect.x + 6, self.rect.y + self.TITLE_H + 4,
                           self.rect.w - 12, self.rect.h - self.TITLE_H - 10)

    def max_scroll(self) -> int:
        n = len(self._entries())
        return max(0, n * self.ROW_H - self._viewport().h)

    def clamp_scroll(self) -> None:
        self.scroll_y = max(0, min(self.scroll_y, self.max_scroll()))

    def _row_rect(self, index: int) -> pygame.Rect:
        vp = self._viewport()
        return pygame.Rect(vp.x + 2,
                           vp.y + index * self.ROW_H - self.scroll_y,
                           vp.w - 8, self.ROW_H - 4)

    # ------------------------------------------------------------------ 事件
    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and \
                event.button in (4, 5):
            step = self.ROW_H * 2
            self.scroll_y += (-step) if event.button == 4 else step
            self.clamp_scroll()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            title_bar = pygame.Rect(self.rect.x, self.rect.y,
                                    self.rect.w, self.TITLE_H)
            if title_bar.collidepoint(event.pos):
                for btn, cb in ((self.btn_close, self.close),
                                (self.btn_refresh, self.refresh_listing)):
                    r = btn.move(self.rect.right - self.BTN_W + 3
                                 if btn is self.btn_close else
                                 self.rect.right - 2 * self.BTN_W + 3,
                                 self.rect.y + 5)
                    if r.collidepoint(event.pos):
                        cb()
                        return True
                return True                      # 标题栏其他区域：吞掉
            if not self.rect.collidepoint(event.pos):
                self.close()                     # 点外部关闭
                return True
            idx = ((event.pos[1] - self._viewport().y + self.scroll_y)
                   // self.ROW_H)
            entries = self._entries()
            if 0 <= idx < len(entries):
                kind, value = entries[idx]
                row = self._row_rect(idx)
                if row.collidepoint(event.pos):
                    if kind == "up":
                        self.rel_dir = "/".join(
                            self.rel_dir.split("/")[:-1])
                        self.scroll_y = 0
                        self.refresh_listing()
                    elif kind == "dir":
                        self.rel_dir = f"{self.rel_dir}/{value}".strip("/")
                        self.scroll_y = 0
                        self.refresh_listing()
                    elif kind == "img":
                        target = self.target or "img"
                        self.on_select(target, value)
                        self.close()
                    return True
            return True                          # 弹层内空白处也吞掉点击
        if event.type in (pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            return True                          # 模态期间吞掉其余鼠标事件
        return False

    # ------------------------------------------------------------------ 绘制
    def _get_overlay(self, size):
        key = tuple(size)
        if key not in self._overlay_cache:
            ov = pygame.Surface(size, pygame.SRCALPHA)
            ov.fill((0, 0, 0, 150))
            self._overlay_cache[key] = ov
        return self._overlay_cache[key]

    @staticmethod
    def _draw_folder_icon(surface: pygame.Surface, center) -> None:
        x, y = center[0] - 22, center[1] - 14
        body = pygame.Rect(x, y + 4, 44, 28)
        tab = pygame.Rect(x, y, 18, 8)
        pygame.draw.rect(surface, (96, 130, 200), tab,
                         border_top_left_radius=3,
                         border_top_right_radius=3)
        pygame.draw.rect(surface, (120, 160, 235), body,
                         border_radius=3)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        surface.blit(self._get_overlay(surface.get_size()), (0, 0))

        pygame.draw.rect(surface, (30, 32, 40), self.rect, border_radius=8)
        pygame.draw.rect(surface, (90, 110, 160), self.rect, 1,
                         border_radius=8)

        # ---- 标题栏：面包屑 + 刷新/关闭
        bar = pygame.Rect(self.rect.x, self.rect.y, self.rect.w,
                          self.TITLE_H)
        pygame.draw.rect(surface, (38, 42, 54), bar,
                         border_top_left_radius=8,
                         border_top_right_radius=8)
        cr = self.btn_close.move(self.rect.right - self.BTN_W + 3,
                                 self.rect.y + 5)
        rr = self.btn_refresh.move(self.rect.right - 2 * self.BTN_W + 3,
                                   self.rect.y + 5)
        for rect, label in ((cr, "X"), (rr, "刷新")):
            pygame.draw.rect(surface, THEME["btn"], rect, border_radius=4)
            col = THEME["btn_text"]
            if label == "X":
                pygame.draw.line(surface, col, (rect.centerx - 5,
                                                rect.centery - 5),
                                 (rect.centerx + 5, rect.centery + 5), 2)
                pygame.draw.line(surface, col, (rect.centerx + 5,
                                                rect.centery - 5),
                                 (rect.centerx - 5, rect.centery + 5), 2)
            else:
                img = get_font(12).render(label, True, col)
                surface.blit(img, img.get_rect(center=rect.center))

        crumb = "assets/" + (self.rel_dir + "/" if self.rel_dir else "")
        img = get_font(13).render(crumb, True, THEME["text_dim"])
        surface.blit(img, (self.rect.x + 10,
                           self.rect.y +
                           (self.TITLE_H - img.get_height()) // 2))

        # ---- 条目列表（裁剪到视口）
        vp = self._viewport()
        old_clip = surface.get_clip()
        surface.set_clip(vp)
        entries = self._entries()
        for i, (kind, value) in enumerate(entries):
            row = self._row_rect(i)
            if row.bottom < vp.y or row.top > vp.bottom:
                continue
            if i % 2 == 1:
                pygame.draw.rect(surface, (36, 39, 48), row, border_radius=4)
            tx = row.x + 64
            if kind == "up":
                pygame.draw.circle(surface, (120, 126, 140),
                                   (row.x + 30, row.centery), 16, 2)
                arr = get_font(16).render("<", True, (200, 205, 215))
                surface.blit(arr, arr.get_rect(
                    center=(row.x + 30, row.centery)))
                _text(surface, ".. 返回上级", (tx, row.centery - 9),
                      THEME["text_dim"])
            elif kind == "dir":
                self._draw_folder_icon(surface,
                                       (row.x + 30, row.centery))
                _text(surface, f"[分类] {value}", (tx, row.centery - 9),
                      THEME["text"])
            else:
                try:
                    thumb = self.assets.get_thumbnail(value, self.THUMB)
                    surface.blit(thumb, thumb.get_rect(
                        center=(row.x + 30, row.centery)))
                    pygame.draw.rect(surface, (70, 76, 92),
                                     thumb.get_rect(
                                         center=(row.x + 30, row.centery)),
                                     1)
                except Exception:
                    pass
                name = value.split("/")[-1]
                sub = value.rsplit("/", 1)[0] if "/" in value else ""
                tcol = (170, 176, 190)
                _text(surface, name, (tx, row.centery - 12), THEME["text"])
                if sub:
                    _text(surface, sub, (tx, row.centery + 7), tcol, 11)
        surface.set_clip(old_clip)

        # ---- 滚动条
        total_h = len(entries) * self.ROW_H
        if total_h > vp.h:
            frac = vp.h / total_h
            thumb_h = max(24, int(vp.h * frac))
            pos = int((vp.h - thumb_h) *
                      (self.scroll_y / max(1, self.max_scroll())))
            pygame.draw.rect(surface, (50, 54, 66),
                             (vp.right - 4, vp.y, 4, vp.h))
            pygame.draw.rect(surface, (110, 150, 230),
                             (vp.right - 4, vp.y + pos, 4, thumb_h))
