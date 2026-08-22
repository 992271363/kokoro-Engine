"""右侧控制面板：只负责改参数、调用 Engine API、显示渲染状态。

面板不实现任何演出逻辑；所有效果均由 kokoro_engine 的公开 API 完成。
"""

from __future__ import annotations

from typing import List, Optional

import pygame

from kokoro_engine import Engine

from .widgets import (THEME, Button, Cycler, Label, ResourceBrowser,
                      Slider, Widget, get_font)

PAD = 10
ROW_H = 28
SECTION_H = 30
GAP = 6
BROWSE_W = 56          # 行尾"浏览"按钮宽度


# 演示用时间轴：覆盖 背景/显示/移动/透明度/层级/隐藏 全部能力
DEMO_TIMELINE = [
    {"bg": "bg/school", "fade": 1.0},
    {"wait": 0.3},
    {"show": "akari", "img": "fg/akari", "pos": "left", "fade": 0.8},
    {"show": "hinata", "img": "fg/hinata", "pos": "right",
     "fade": 0.8, "z": 5},
    {"parallel": [
        {"move": "akari", "to": "center", "dur": 1.6},
        {"alpha": "hinata", "value": 110, "dur": 1.6},
    ]},
    {"layer": "hinata", "op": "front"},
    {"wait": 0.4},
    {"parallel": [
        {"move": "akari", "to": "right", "dur": 1.4},
        {"move": "hinata", "to": "left", "dur": 1.4},
        {"alpha": "hinata", "value": 255, "dur": 1.2},
    ]},
    {"hide": "hinata", "fade": 1.0},
    {"bg": "bg/night", "fade": 1.5},
]


class ControlPanel:
    def __init__(self, engine: Engine, rect: pygame.Rect,
                 browser_rect: Optional[pygame.Rect] = None,
                 on_preset_change=None,
                 desktop_size=(0, 0)) -> None:
        self.engine = engine
        self.rect = pygame.Rect(rect)
        self.widgets: List[Widget] = []
        self.browser = ResourceBrowser(
            browser_rect or self._default_browser_rect(),
            engine.assets, self._on_browser_select)

        # 分辨率预设切换（窗口管理由回调持有方完成）
        self.on_preset_change = on_preset_change
        self.desktop_w, self.desktop_h = desktop_size
        self.pending_resolution: Optional[str] = None

        # 面板参数状态（仅是待提交的参数，不是演出逻辑）
        self.pending_bg: Optional[str] = None
        self.bg_fade = 1.0
        self.show_img: Optional[str] = None
        self.fade_dur = 0.8
        self.place_preset = "center"
        self.move_to = "right"
        self.move_dur = 1.5
        self.sel_sid: Optional[str] = None

        self._build()
        self._status_text = ""
        self.browser_anchor: Optional[pygame.Rect] = None  # 主循环更新

    @property
    def modal_open(self) -> bool:
        return self.browser.modal_open

    def _recenter_browser(self) -> None:
        """按主循环提供的舞台显示区把弹层重新居中（窗口缩放后仍正确）。"""
        if self.browser_anchor is not None:
            r = pygame.Rect(self.browser.rect)
            r.center = self.browser_anchor.center
            self.browser.rect = r

    def _default_browser_rect(self) -> pygame.Rect:
        return pygame.Rect(self.rect.x - 424, self.rect.y + 40, 400, 480)

    def set_rect(self, rect) -> None:
        """窗口尺寸/菜单栏显隐变化时更新面板矩形。

        所有控件整体平移，保持相对布局（Slider 内部几何同步）。
        """
        rect = pygame.Rect(rect)
        dx, dy = rect.x - self.rect.x, rect.y - self.rect.y
        self.rect = rect
        if dx or dy:
            for w in self.widgets:
                if hasattr(w, "move_by"):
                    w.move_by(dx, dy)
                else:
                    w.rect.move_ip(dx, dy)

    # ------------------------------------------------------------------ 布局
    def _add(self, w: Widget) -> Widget:
        self.widgets.append(w)
        return w

    def _section(self, title: str, y: int) -> int:
        r = pygame.Rect(self.rect.x + PAD, y, self.rect.w - 2 * PAD, SECTION_H)
        self._add(Label("▎" + title, r.inflate((-2, -6)), size=15,
                        color="accent"))
        return y + SECTION_H

    def _row(self, y: int) -> pygame.Rect:
        return pygame.Rect(self.rect.x + PAD, y, self.rect.w - 2 * PAD, ROW_H)

    def _half(self, row: pygame.Rect, idx: int, total: int) -> pygame.Rect:
        gap = 8
        w = (row.w - gap * (total - 1)) // total
        return pygame.Rect(row.x + idx * (w + gap), row.y, w, row.h)

    def _build(self) -> None:
        y = self.rect.y + PAD
        inner_w = self.rect.w - 2 * PAD

        # ------------------------------------------------------ 画布分辨率
        y = self._section("画布分辨率", y)
        presets = Engine.RESOLUTION_PRESETS
        self.res_options = [f"{p[0]}×{p[1]}" for p in presets]
        self._res_map = dict(zip(self.res_options, presets))
        cur = f"{self.engine.size[0]}×{self.engine.size[1]}"
        self.pending_resolution = cur if cur in self.res_options \
            else self.res_options[0]
        row = self._row(y)
        cyc_rect = pygame.Rect(row.x, row.y, row.w - BROWSE_W - 6, row.h)
        idx = self.res_options.index(self.pending_resolution)
        self.cyc_res = self._add(Cycler(
            "预设", cyc_rect, self.res_options, idx,
            on_change=lambda v: setattr(self, "pending_resolution", v)))
        self.btn_apply_res = self._add(Button(
            "应用",
            pygame.Rect(row.right - BROWSE_W, row.y, BROWSE_W, row.h),
            self._on_apply_resolution))
        y += ROW_H + GAP + 8

        # ---------------------------------------------------------- 背景
        y = self._section("背景", y)
        bg_names = self.engine.assets.all_images("bg")
        if self.pending_bg is None and bg_names:
            self.pending_bg = bg_names[0]
        row = self._row(y)
        cyc_rect = pygame.Rect(row.x, row.y, row.w - BROWSE_W - 6, row.h)
        self.cyc_bg = self._add(Cycler(
            "背景图", cyc_rect, bg_names, 0,
            on_change=lambda v: setattr(self, "pending_bg", v)))
        self.btn_browse_bg = self._add(Button(
            "浏览",
            pygame.Rect(row.right - BROWSE_W, row.y, BROWSE_W, row.h),
            self._on_browse_bg))
        y += ROW_H + GAP
        self.sld_bg_fade = self._add(Slider(
            "切换时长", self._row(y), 0.0, 3.0, self.bg_fade,
            on_change=lambda v: setattr(self, "bg_fade", v),
            fmt=lambda v: f"{v:.1f}s"))
        y += ROW_H + GAP
        self.btn_apply_bg = self._add(Button(
            "应用背景（交叉淡入淡出）", self._row(y), self._on_apply_bg))
        y += ROW_H + GAP + 8

        # ------------------------------------------------ 立绘：显示与关闭
        y = self._section("立绘 · 显示 / 关闭", y)
        chars = self.engine.assets.all_images("fg")
        if self.show_img is None and chars:
            self.show_img = chars[0]
        row = self._row(y)
        cyc_rect = pygame.Rect(row.x, row.y, row.w - BROWSE_W - 6, row.h)
        self.cyc_img = self._add(Cycler(
            "立绘图片", cyc_rect, chars, 0,
            on_change=lambda v: setattr(self, "show_img", v)))
        self.btn_browse_img = self._add(Button(
            "浏览",
            pygame.Rect(row.right - BROWSE_W, row.y, BROWSE_W, row.h),
            self._on_browse_img))
        y += ROW_H + GAP
        r = self._row(y)
        self.btn_show = self._add(Button(
            "显示（淡入）", self._half(r, 0, 3), self._on_show))
        self.btn_hide = self._add(Button(
            "关闭（淡出）", self._half(r, 1, 3), self._on_hide))
        self.btn_remove = self._add(Button(
            "立即移除", self._half(r, 2, 3), self._on_remove))
        y += ROW_H + GAP
        self.sld_fade_dur = self._add(Slider(
            "淡入淡出时长", self._row(y), 0.05, 3.0, self.fade_dur,
            on_change=lambda v: setattr(self, "fade_dur", v),
            fmt=lambda v: f"{v:.2f}s"))
        y += ROW_H + GAP + 8

        # ---------------------------------------------- 选中立绘：摆放等
        y = self._section("选中立绘 · 摆放 / 移动 / 叠放", y)
        self.lbl_sel = self._add(Label("当前未选择立绘", self._row(y),
                                       size=12, color="text_dim"))
        y += ROW_H + GAP - 4
        sw, sh = self.engine.size
        self.cyc_sel = self._add(Cycler(
            "目标立绘", self._row(y), [], 0, on_change=self._on_pick_sprite))
        y += ROW_H + GAP
        self.cyc_place = self._add(Cycler(
            "摆放预设", self._row(y), ["left", "center", "right"], 1,
            on_change=self._on_place_preset))
        y += ROW_H + GAP
        r = self._row(y)
        self.btn_place = self._add(Button(
            "放到预设位", self._half(r, 0, 2), self._on_place))
        self.btn_front = self._add(Button(
            "置顶", self._half(r, 1, 2), lambda: self._layer_op("front")))
        y += ROW_H + GAP
        r = self._row(y)
        self.btn_back = self._add(Button(
            "置底", self._half(r, 0, 2), lambda: self._layer_op("back")))
        self.btn_updown = self._add(Button(
            "上移一层 ⇄ 下移一层", self._half(r, 1, 2),
            lambda: self._layer_op("toggle")))
        y += ROW_H + GAP
        self.sld_x = self._add(Slider(
            "X 坐标", self._row(y), 0, float(sw), 0,
            on_change=self._on_drag_x, fmt=lambda v: f"{v:.0f}"))
        y += ROW_H + GAP
        self.sld_y = self._add(Slider(
            "Y 脚线", self._row(y), 0, float(sh), 0,
            on_change=self._on_drag_y, fmt=lambda v: f"{v:.0f}"))
        y += ROW_H + GAP + 8

        # -------------------------------------------------------- 平滑移动
        y = self._section("平滑移动", y)
        self.cyc_move_to = self._add(Cycler(
            "移动到", self._row(y), ["left", "center", "right"], 2,
            on_change=lambda v: setattr(self, "move_to", v)))
        y += ROW_H + GAP
        self.sld_move_dur = self._add(Slider(
            "移动时长", self._row(y), 0.1, 5.0, self.move_dur,
            on_change=lambda v: setattr(self, "move_dur", v),
            fmt=lambda v: f"{v:.2f}s"))
        y += ROW_H + GAP
        self.btn_move = self._add(Button(
            "开始移动", self._row(y), self._on_move))
        y += ROW_H + GAP + 8

        # ---------------------------------------------------------- 时间轴
        y = self._section("时间轴序列", y)
        r = self._row(y)
        self.btn_demo = self._add(Button(
            "▶ 播放演示", self._half(r, 0, 3), self._on_play_demo))
        self.btn_tl_pause = self._add(Button(
            "⏸ 暂停", self._half(r, 1, 3), self._on_timeline_pause))
        self.btn_tl_stop = self._add(Button(
            "■ 停止", self._half(r, 2, 3), self._on_timeline_stop))
        y += ROW_H + GAP
        self.lbl_timeline = self._add(Label("", self._row(y), size=12,
                                            color="text_dim"))
        y += ROW_H + GAP
        self.btn_pause_all = self._add(Button(
            "⏸ 全局暂停全部动画", self._row(y), self._on_toggle_global))
        y += ROW_H + GAP

        self.content_bottom = y

    # ------------------------------------------------------------------ 回调
    def _selected_sprite(self):
        return self.engine.stage.get_sprite(self.sel_sid) \
            if self.sel_sid else None

    def select_sprite(self, sid: Optional[str]) -> None:
        """外部（如点击舞台拾取）设置当前选中立绘。"""
        self.sel_sid = sid
        self._sync_selection_ui()
        ids = [s.id for s in self.engine.stage.sorted_sprites()]
        if sid in ids:
            self.cyc_sel.index = ids.index(sid)

    def _on_apply_bg(self) -> None:
        imgs = self.engine.assets.all_images("bg")
        name = self.pending_bg or (imgs[0] if imgs else None)
        if name:
            self.engine.set_background(name, fade=self.bg_fade)

    def _auto_id(self, image: str) -> str:
        base = image.split("/")[-1] or "sprite"
        sid, i = base, 1
        while self.engine.stage.has_sprite(sid):
            i += 1
            sid = f"{base}_{i}"
        return sid

    def _on_show(self) -> None:
        imgs = self.engine.assets.all_images("fg")
        img = self.show_img or (imgs[0] if imgs else None)
        if not img:
            return
        sid = self._auto_id(img)
        self.engine.show_sprite(sid, image=img,
                                pos=self.place_preset,
                                fade=self.fade_dur)
        self.sel_sid = sid
        self._sync_selection_ui()

    def _on_hide(self) -> None:
        spr = self._selected_sprite()
        if spr:
            self.engine.hide_sprite(spr.id, fade=self.fade_dur)

    def _on_remove(self) -> None:
        spr = self._selected_sprite()
        if spr:
            self.engine.remove_sprite(spr.id)

    def _on_pick_sprite(self, value: Optional[str]) -> None:
        self.sel_sid = value if value in {
            s.id for s in self.engine.stage.sorted_sprites()} else None
        self._sync_selection_ui()

    def _on_place_preset(self, value: str) -> None:
        self.place_preset = value

    def _on_place(self) -> None:
        spr = self._selected_sprite()
        if not spr:
            return
        x, yb = self.engine.stage.preset_xy(self.place_preset)
        self.engine.tweens.kill(spr, "x")
        self.engine.tweens.kill(spr, "y")
        spr.x, spr.y = x, yb

    def _layer_op(self, op: str) -> None:
        spr = self._selected_sprite()
        if not spr:
            return
        if op == "front":
            self.engine.bring_to_front(spr.id)
        elif op == "back":
            self.engine.send_to_back(spr.id)
        elif op == "toggle":
            front_ids = self.engine.stage.sprite_ids()   # 前→后
            if front_ids and front_ids[0] == spr.id:
                self.engine.layer_down(spr.id)
            else:
                self.engine.layer_up(spr.id)

    def _on_drag_x(self, v: float) -> None:
        spr = self._selected_sprite()
        if spr:
            self.engine.tweens.kill(spr, "x")
            spr.x = v

    def _on_drag_y(self, v: float) -> None:
        spr = self._selected_sprite()
        if spr:
            self.engine.tweens.kill(spr, "y")
            spr.y = v

    def _on_move(self) -> None:
        spr = self._selected_sprite()
        if spr:
            self.engine.move_sprite(spr.id, to=self.move_to,
                                    dur=self.move_dur)

    def _on_play_demo(self) -> None:
        self.engine.play(DEMO_TIMELINE)

    def _on_timeline_pause(self) -> None:
        paused = self.engine.timeline.toggle_pause()
        self.btn_tl_pause.text = "▶ 继续" if paused else "⏸ 暂停"

    def _on_timeline_stop(self) -> None:
        self.engine.stop_timeline()
        self.btn_tl_pause.text = "⏸ 暂停"

    def _on_toggle_global(self) -> None:
        paused = self.engine.toggle_pause()
        self.btn_pause_all.text = ("▶ 继续全部动画" if paused
                                   else "⏸ 全局暂停全部动画")

    # ------------------------------------------------------------------ 同步
    def _sync_selection_ui(self) -> None:
        """把选中立绘的实时值写进滑块，并刷新目标立绘列表。"""
        ids = self.engine.stage.sprite_ids()          # 前→后
        self.cyc_sel.set_options(ids, keep_value=True)
        if self.sel_sid not in ids:
            self.sel_sid = ids[0] if ids else None
            self.cyc_sel.index = ids.index(self.sel_sid) \
                if ids else 0
        spr = self._selected_sprite()
        if spr:
            self.lbl_sel.text = (f"已选 {spr.id}（图:{spr.name} z={spr.z:g} "
                                 f"alpha={spr.alpha:.0f}）")
            self.btn_hide.enabled = True
            self.btn_remove.enabled = True
            self.btn_place.enabled = True
            self.btn_move.enabled = True
            for b in (self.btn_front, self.btn_back, self.btn_updown):
                b.enabled = True
            if not self.sld_x._dragging:
                self.sld_x.set_value(spr.x)
            if not self.sld_y._dragging:
                self.sld_y.set_value(spr.y)
        else:
            self.lbl_sel.text = "当前未选择立绘"
            for b in (self.btn_hide, self.btn_remove, self.btn_place,
                      self.btn_move, self.btn_front, self.btn_back,
                      self.btn_updown):
                b.enabled = False

    def update(self, dt: float) -> None:
        self._sync_resolution_ui()
        self._sync_selection_ui()

        st = self.engine.get_state()
        tl = st["timeline_state"]
        prog = st["timeline_progress"]
        parts = [
            f"时间轴: {tl} {prog}",
            f"全局{'已暂停' if st['paused'] else '运行中'}",
        ]
        if st["bg_transitioning"]:
            parts.append("背景切换中…")
        self.lbl_timeline.text = "  |  ".join(parts)

        # 时间轴播放时禁用演示按钮，避免叠加播放
        self.btn_demo.enabled = tl not in ("playing", "paused")
        self.btn_tl_stop.enabled = tl != "idle"

    # ------------------------------------------------------------------ 事件
    def handle_event(self, event: pygame.event.Event) -> bool:
        # 模态弹层最优先（它可能覆盖面板/舞台区域）
        if self.browser.handle_event(event):
            return True
        consumed = False
        for w in reversed(self.widgets):
            if w.handle_event(event):
                consumed = True
                if event.type in (pygame.MOUSEBUTTONDOWN,
                                  pygame.MOUSEBUTTONUP):
                    break     # 单击只交给一个控件
        return consumed

    def _on_browse_bg(self) -> None:
        self._recenter_browser()
        self.browser.open("bg")

    def _on_browse_img(self) -> None:
        self._recenter_browser()
        self.browser.open("img")

    def _on_browser_select(self, target: str, key: str) -> None:
        """浏览器选中资源：写入对应槽位并同步 Cycler 显示。"""
        kind = "bg" if target == "bg" else "fg"
        cyc = self.cyc_bg if target == "bg" else self.cyc_img
        opts = self.engine.assets.all_images(kind)
        cyc.set_options(opts, keep_value=True)
        if key in cyc.options:
            cyc.index = cyc.options.index(key)
        if target == "bg":
            self.pending_bg = key
        else:
            self.show_img = key

    # -------------------------------------------------------- 画布分辨率
    def _preset_fits(self, preset) -> bool:
        """桌面尺寸未知（dummy 等）时不限制。"""
        return (self.desktop_w <= 0 or self.desktop_h <= 0
                or (preset[0] <= self.desktop_w
                    and preset[1] <= self.desktop_h))

    def _on_apply_resolution(self) -> None:
        target = self._res_map.get(self.pending_resolution)
        if target is None or tuple(target) == tuple(self.engine.size):
            return
        if not self._preset_fits(target):
            return
        if self.on_preset_change is not None:
            self.on_preset_change(tuple(target))

    def _sync_resolution_ui(self) -> None:
        target = self._res_map.get(self.pending_resolution)
        self.btn_apply_res.enabled = (
            target is not None
            and tuple(target) != tuple(self.engine.size)
            and self._preset_fits(target))

    # ------------------------------------------------------------------ 绘制
    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, THEME["panel_bg"], self.rect)
        pygame.draw.line(surface, (45, 48, 58),
                         (self.rect.x, self.rect.y),
                         (self.rect.x, self.rect.bottom))
        # 分隔线（按 section label 的位置）
        for w in self.widgets:
            if isinstance(w, Label) and w.text.startswith("▎"):
                pygame.draw.line(surface, (40, 44, 54),
                                 (w.rect.x - 2, w.rect.top - 3),
                                 (self.rect.right - PAD, w.rect.top - 3))
        for w in self.widgets:
            w.draw(surface)
        # 弹层最后画，保证在最上层
        self.browser.draw(surface)
