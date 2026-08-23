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

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

if sys.platform == "win32":
    # 声明 DPI 感知（必须在任何 pygame 视频初始化之前）：
    # 否则 Windows 显示缩放(125%/150%…)会把桌面尺寸虚拟化，
    # 导致 pygame.display.Info() 报告错误的分辨率、窗口被位图拉伸发虚。
    os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Win8.1+ 按显示器感知
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()         # Vista+ 兜底
    except Exception:
        pass

import pygame  # noqa: E402

from gui.panel import ControlPanel  # noqa: E402
from gui.widgets import get_font, set_ui_scale, s as ui_s  # noqa: E402
from kokoro_engine import Engine  # noqa: E402
from kokoro_engine.renderer import StageRenderer  # noqa: E402

ASSET_DIR = os.path.join(ROOT, "assets")

MIN_WINDOW_SIZE = (960, 540)          # 最小窗口（16:9，物理像素）
STATUS_BAR_H = 32                     # 底部状态栏占位（逻辑值，经 ui_s 缩放）
PANEL_W = 432                         # 面板宽度（逻辑值）
MARGIN = 20                           # 页边距（逻辑值）
TARGET_FPS = 120                      # 渲染帧率上限（逻辑步长固定 60Hz，见 Engine.SIM_HZ）

BG_COLOR = (16, 17, 20)
WINDOW_TITLE = "kokoro-Engine v0.3 · galgame 演出系统"


def detect_windows_ui_scale() -> float:
    """读取 Windows 显示缩放（96DPI=100% 基准）。

    仅用于编辑器 GUI（字体/控件/间距）的放大；
    非 Windows / 检测失败时返回 1.0。
    """
    if sys.platform != "win32":
        return 1.0
    try:
        import ctypes
        dpi = int(ctypes.windll.user32.GetDpiForSystem())
        if dpi > 0:
            return max(1.0, dpi / 96.0)
    except Exception:
        pass
    try:
        import ctypes
        sf = int(ctypes.windll.shcore.GetScaleFactorForDevice(0))
        if sf > 0:
            return max(1.0, sf / 100.0)
    except Exception:
        pass
    return 1.0


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


CHROME_TITLE_H = 48      # 系统窗口标题栏 + 安全余量（物理像素）
CHROME_PAD_W = 16        # 水平安全余量


def get_work_area():
    """主显示器工作区 (宽, 高)——已排除任务栏。

    失败时回退为整屏尺寸。
    """
    if sys.platform == "win32":
        try:
            import ctypes

            class _RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long),
                            ("top", ctypes.c_long),
                            ("right", ctypes.c_long),
                            ("bottom", ctypes.c_long)]

            rect = _RECT()
            # 0x0030 = SPI_GETWORKAREA
            if ctypes.windll.user32.SystemParametersInfoW(
                    0x0030, 0, ctypes.byref(rect), 0):
                w, h = rect.right - rect.left, rect.bottom - rect.top
                if w > 0 and h > 0:
                    return max(1, w), max(1, h)
        except Exception:
            pass
    try:
        info = pygame.display.Info()
        return max(1, info.current_w), max(1, info.current_h)
    except Exception:
        return MIN_WINDOW_SIZE


def fit_window_to_work(w: int, h: int, wa_w: int, wa_h: int) -> tuple:
    """把期望窗口尺寸收缩到工作区可容纳的最大 16:9 尺寸。

    已能容纳时原样返回；画布分辨率不受影响（显示层等比缩放）。
    结果不低于最小窗口（极端小屏兜底允许溢出）。
    """
    w, h = max(int(w), 1), max(int(h), 1)
    aw = max(1, wa_w - CHROME_PAD_W)
    ah = max(1, wa_h - CHROME_TITLE_H)
    if w <= aw and h <= ah:
        return w, h
    scale = min(aw / w, ah / h)
    fw = max(1, int(w * scale))
    fh = max(1, int(h * scale))
    return (max(fw, MIN_WINDOW_SIZE[0]), max(fh, MIN_WINDOW_SIZE[1]))


def compute_layout(win_w: int, win_h: int, canvas: tuple) -> tuple:
    """返回 (panel_rect, disp_rect)。舞台显示区等比缩放并居中。

    GUI 布局尺寸经 ui_s() 缩放；Stage 画布与显示缩放不受影响。
    """
    cw, chh = canvas
    margin = ui_s(MARGIN)
    panel_w = ui_s(PANEL_W)
    status_h = ui_s(STATUS_BAR_H)
    panel_x = win_w - panel_w - margin
    panel_rect = pygame.Rect(panel_x, margin, panel_w,
                             max(ui_s(220), win_h - margin * 2))
    avail = pygame.Rect(margin, margin,
                        max(ui_s(160), panel_x - margin * 2 - ui_s(12)),
                        max(ui_s(90), win_h - margin - status_h))
    scale = min(avail.w / cw, avail.h / chh)
    disp = pygame.Rect(0, 0,
                       max(ui_s(64), int(cw * scale)),
                       max(ui_s(36), int(chh * scale)))
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
    # GUI 缩放：按 Windows DPI 放大编辑器字体/控件/间距（Stage 不受影响）
    set_ui_scale(detect_windows_ui_scale())

    info = pygame.display.Info()
    work_w, work_h = get_work_area()
    preset0 = choose_startup_preset(info.current_w, info.current_h)
    # 画布 = 预设分辨率；窗口收缩到工作区内（不遮挡任务栏/标题栏）
    win0_w, win0_h = fit_window_to_work(*preset0, work_w, work_h)
    screen = pygame.display.set_mode((win0_w, win0_h), pygame.RESIZABLE)
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    engine = Engine(asset_dir=ASSET_DIR, stage_size=preset0)
    renderer = StageRenderer(engine)

    desktop_w, desktop_h = max(0, info.current_w), max(0, info.current_h)
    panel_rect, disp = compute_layout(*screen.get_size(), engine.size)
    disp_surface = pygame.Surface(disp.size)   # 显示分辨率合成目标

    def apply_preset(p) -> None:
        """面板分辨率回调：切逻辑画布，窗口自适应工作区。"""
        nonlocal screen
        if tuple(engine.size) != p:
            engine.resize_stage(p)
        ww, wh = fit_window_to_work(*p, work_w, work_h)
        new_screen = _apply_window_size(ww, wh)
        if new_screen is not None:
            screen = new_screen

    panel = ControlPanel(engine, panel_rect,
                         browser_rect=pygame.Rect(
                             0, 0, ui_s(400), ui_s(460)),
                         on_preset_change=apply_preset,
                         desktop_size=(desktop_w, desktop_h))
    drag = StageDragController(engine, panel)

    resize_types = {getattr(pygame, n) for n in ("VIDEORESIZE",
                                                 "WINDOWRESIZED")
                    if hasattr(pygame, n)}

    running = True
    while running:
        dt = min(clock.tick(TARGET_FPS) / 1000.0, 0.25)
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
                if drag.active:
                    # 拖拽进行中：移动跟随，松开结束（优先于面板/弹层）
                    if event.type == pygame.MOUSEMOTION:
                        drag.motion(disp, *event.pos)
                    elif event.type == pygame.MOUSEBUTTONUP and \
                            event.button == 1:
                        drag.end()
                    continue
                if panel.modal_open:
                    panel.handle_event(event)       # 弹层打开时全部给弹层
                    continue
                if panel.rect.collidepoint(event.pos):
                    panel.handle_event(event)
                elif event.type == pygame.MOUSEBUTTONDOWN \
                        and event.button == 1 \
                        and disp.collidepoint(event.pos):
                    drag.begin(disp, *event.pos)    # 拾取并进入拖拽

        sim_alpha = engine.advance(dt)   # 固定步长推进 + 帧间插值因子
        panel.update(dt)
        panel.browser_anchor = disp

        # 布局每帧同步（窗口尺寸变化）
        panel_rect_n, disp_n = compute_layout(win_w, win_h, engine.size)
        panel.set_rect(panel_rect_n)
        disp = disp_n

        # ------------------------------------------------------------ 渲染
        screen.fill(BG_COLOR)
        if disp_surface.get_size() != disp.size:
            disp_surface = pygame.Surface(disp.size)
        renderer.draw(disp_surface, disp, sim_alpha)
        screen.blit(disp_surface, disp.topleft)
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


def screen_to_stage(disp_rect: pygame.Rect, engine: Engine,
                    px: float, py: float) -> tuple:
    """屏幕坐标 → 画布坐标（考虑显示缩放）。"""
    return ((px - disp_rect.x) * engine.size[0] / max(1, disp_rect.w),
            (py - disp_rect.y) * engine.size[1] / max(1, disp_rect.h))


def pick_sprite_at(engine: Engine, sx: float, sy: float):
    """画布坐标处自前向后拾取立绘，未命中返回 None。"""
    for spr in reversed(engine.stage.sorted_sprites()):
        if spr.contains_point(sx, sy):
            return spr
    return None


class StageDragController:
    """舞台预览区鼠标拖拽立绘：按下选中并抓取，移动跟随，松开结束。

    保持抓取偏移（手按在哪一点，立绘相对该点不动）；
    小于阈值的位移视为纯点击选中等价行为。
    """

    DRAG_THRESHOLD = 3      # 屏幕像素

    def __init__(self, engine: Engine, panel: ControlPanel) -> None:
        self.engine = engine
        self.panel = panel
        self.active = False
        self._sid = None
        self._off = (0.0, 0.0)
        self._start = (0.0, 0.0)
        self._moved = False

    def begin(self, disp_rect: pygame.Rect, px: float, py: float) -> bool:
        sx, sy = screen_to_stage(disp_rect, self.engine, px, py)
        spr = pick_sprite_at(self.engine, sx, sy)
        self.panel.select_sprite(spr.id if spr is not None else None)
        if spr is None:
            return False
        # 手动拖动接管移动动画
        self.engine.tweens.kill(spr, "x")
        self.engine.tweens.kill(spr, "y")
        self._sid = spr.id
        self._off = (spr.x - sx, spr.y - sy)
        self._start = (px, py)
        self._moved = False
        self.active = True
        return True

    def motion(self, disp_rect: pygame.Rect, px: float,
               py: float) -> None:
        if not self.active:
            return
        if not self._moved:
            if ((px - self._start[0]) ** 2 +
                    (py - self._start[1]) ** 2) < \
                    self.DRAG_THRESHOLD ** 2:
                return
            self._moved = True
        spr = self.engine.stage.get_sprite(self._sid)
        if spr is None:
            self.end()
            return
        sx, sy = screen_to_stage(disp_rect, self.engine, px, py)
        spr.x = sx + self._off[0]
        spr.y = sy + self._off[1]
        spr.snap_render()                # 拖拽即时贴合，无插值拖影

    def end(self) -> None:
        self.active = False
        self._sid = None


if __name__ == "__main__":
    sys.exit(main())
