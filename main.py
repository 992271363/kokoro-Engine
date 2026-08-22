"""kokoro-Engine 演示入口。

16:9 固定比例编辑器窗口：
- 分辨率预设 = 引擎逻辑画布（1280×720 ~ 2560×1440），默认 1920×1080，
  切换入口在右侧控制面板顶部的"画布分辨率"区；
- 窗口可自由拖拽，但始终吸附回 16:9，画布坐标不随窗口缩放变化。

运行：python main.py
"""

from __future__ import annotations

import os
import sys

import pygame

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from gui.panel import ControlPanel  # noqa: E402
from gui.widgets import get_font  # noqa: E402
from kokoro_engine import Engine  # noqa: E402

ASSET_DIR = os.path.join(ROOT, "assets")

MIN_WINDOW_SIZE = (960, 540)          # 最小窗口（16:9）
STATUS_BAR_H = 32                     # 底部状态栏占位
PANEL_W = 432
MARGIN = 20

BG_COLOR = (16, 17, 20)
WINDOW_TITLE = "kokoro-Engine v0.3 · galgame 演出系统"


# ------------------------------------------------------------------ 几何工具
def snap_16_9(w: int, h: int, min_size=MIN_WINDOW_SIZE) -> tuple:
    """把拖拽出的任意窗口尺寸吸附回最近的 16:9（保留偏差小的维度）。"""
    w = max(int(w), min_size[0])
    h = max(int(h), min_size[1])
    keep_w = (w, int(w * 9 / 16 + 0.5))      # 保宽调高
    keep_h = (int(h * 16 / 9 + 0.5), h)      # 保高调宽
    dev_keep_w = abs(h - keep_w[1])          # 保宽时需要修改的高度量
    dev_keep_h = abs(w - keep_h[0])          # 保高时需要修改的宽度量
    pick = keep_h if dev_keep_h <= dev_keep_w else keep_w
    return max(pick[0], min_size[0]), max(pick[1], min_size[1])


def choose_startup_preset(desk_w: int, desk_h: int) -> tuple:
    """启动分辨率：默认 1920×1080；屏幕放不下则取能容纳的最大预设。"""
    if desk_w <= 0 or desk_h <= 0:           # dummy 驱动等无桌面信息
        return Engine.DEFAULT_STAGE_SIZE
    for p in sorted(Engine.RESOLUTION_PRESETS, reverse=True):
        if p[0] <= desk_w and p[1] <= desk_h:
            return p
    return MIN_WINDOW_SIZE


def compute_layout(win_w: int, win_h: int, canvas: tuple) -> tuple:
    """返回 (panel_rect, disp_rect)。舞台显示区等比缩放并居中。"""
    cw, chh = canvas
    panel_x = win_w - PANEL_W - MARGIN
    panel_rect = pygame.Rect(panel_x, MARGIN, PANEL_W,
                             max(220, win_h - MARGIN * 2))
    avail = pygame.Rect(MARGIN, MARGIN,
                        max(160, panel_x - MARGIN * 2 - 12),
                        max(90, win_h - MARGIN - STATUS_BAR_H))
    scale = min(avail.w / cw, avail.h / chh)
    disp = pygame.Rect(0, 0,
                       max(64, int(cw * scale)),
                       max(36, int(chh * scale)))
    disp.center = avail.center
    return panel_rect, disp


def resize_event_size(event) -> tuple:
    """兼容两种缩放事件：WINDOWRESIZED 用 x/y，VIDEORESIZE 用 w/h。"""
    w = getattr(event, "w", None)
    if w is not None and hasattr(event, "h"):
        return int(w), int(event.h)
    return int(getattr(event, "x", 0)), int(getattr(event, "y", 0))


def _apply_window_size(w: int, h: int):
    """程序化改窗口大小；优先 Window API（不重建渲染上下文）。"""
    try:
        pygame.Window.from_display_module().size = (w, h)
        return None
    except Exception:
        return pygame.display.set_mode((w, h), pygame.RESIZABLE)


# ------------------------------------------------------------------ 主程序
def main() -> int:
    pygame.init()
    info = pygame.display.Info()
    preset0 = choose_startup_preset(info.current_w, info.current_h)
    screen = pygame.display.set_mode(preset0, pygame.RESIZABLE)
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    engine = Engine(asset_dir=ASSET_DIR, stage_size=preset0)
    stage_surface = pygame.Surface(engine.size)

    desktop_w, desktop_h = max(0, info.current_w), max(0, info.current_h)
    panel_rect, disp = compute_layout(*screen.get_size(), engine.size)

    def apply_preset(p) -> None:
        """面板分辨率回调：切逻辑画布并让窗口 1:1 跟随。"""
        nonlocal screen, stage_surface
        if tuple(engine.size) != p:
            engine.resize_stage(p)
            stage_surface = pygame.Surface(engine.size)
        new_screen = _apply_window_size(*p)
        if new_screen is not None:
            screen = new_screen

    panel = ControlPanel(engine, panel_rect,
                         browser_rect=pygame.Rect(0, 0, 400, 460),
                         on_preset_change=apply_preset,
                         desktop_size=(desktop_w, desktop_h))

    resize_types = {getattr(pygame, n) for n in ("VIDEORESIZE",
                                                 "WINDOWRESIZED")
                    if hasattr(pygame, n)}

    # 开场演出：即时背景 + 左侧立绘淡入
    engine.set_background("bg/school", fade=0.0)
    engine.show_sprite("akari", image="fg/akari", pos="left", fade=1.2)
    panel.select_sprite("akari")

    running = True
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        win_w, win_h = screen.get_size()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue
            if event.type in resize_types:
                sw, sh = resize_event_size(event)
                tw, th = snap_16_9(sw, sh)
                cur = screen.get_size()
                if abs(cur[0] - tw) > 1 or abs(cur[1] - th) > 1:
                    new_screen = _apply_window_size(tw, th)
                    if new_screen is not None:
                        screen = new_screen
                continue
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    panel._on_toggle_global()
                continue
            if event.type in (pygame.MOUSEBUTTONDOWN,
                              pygame.MOUSEBUTTONUP,
                              pygame.MOUSEMOTION):
                if panel.modal_open:
                    panel.handle_event(event)       # 弹层打开时全部给弹层
                    continue
                if panel.rect.collidepoint(event.pos):
                    panel.handle_event(event)
                elif event.type == pygame.MOUSEBUTTONDOWN \
                        and event.button == 1 \
                        and disp.collidepoint(event.pos):
                    _pick_sprite(panel, engine, disp, *event.pos)

        engine.update(dt)
        panel.update(dt)

        # 布局每帧同步（窗口尺寸变化）
        panel_rect_n, disp_n = compute_layout(win_w, win_h, engine.size)
        panel.set_rect(panel_rect_n)
        disp = disp_n

        # ------------------------------------------------------------ 渲染
        screen.fill(BG_COLOR)
        engine.draw(stage_surface)
        if disp.size == engine.size:
            screen.blit(stage_surface, disp.topleft)
        else:
            scaled = pygame.transform.smoothscale(stage_surface,
                                                  disp.size)
            screen.blit(scaled, disp.topleft)
        pygame.draw.rect(screen, (70, 76, 92), disp, 1)

        zoom = disp.w / max(1, engine.size[0]) * 100
        st = engine.get_state()
        hint = (f"背景: {st['bg'] or '无'}   立绘: {len(st['sprites'])}   "
                f"补间: {engine.tweens.active_count}   "
                f"画布 {engine.size[0]}×{engine.size[1]} ({zoom:.0f}%)   "
                f"FPS: {clock.get_fps():.0f}   （空格=暂停 Esc=退出）")
        screen.blit(get_font(13).render(hint, True, (150, 156, 168)),
                    (disp.x, disp.bottom + 8))

        panel.draw(screen)
        pygame.display.flip()

    pygame.quit()
    return 0


def _pick_sprite(panel: ControlPanel, engine: Engine,
                 disp_rect: pygame.Rect, px: int, py: int) -> None:
    """屏幕坐标 → 画布坐标（考虑显示缩放），前→后拾取立绘。"""
    sx = (px - disp_rect.x) * engine.size[0] / max(1, disp_rect.w)
    sy = (py - disp_rect.y) * engine.size[1] / max(1, disp_rect.h)
    for spr in reversed(engine.stage.sorted_sprites()):
        if spr.contains_point(sx, sy):
            panel.select_sprite(spr.id)
            return
    panel.select_sprite(None)


if __name__ == "__main__":
    sys.exit(main())
