"""无头冒烟测试：用 SDL dummy 驱动跑通引擎全部 API。

运行：python tests/smoke_test.py
"""

from __future__ import annotations

import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from kokoro_engine import Engine  # noqa: E402
from kokoro_engine.assets import (FALLBACK_BACKGROUNDS,  # noqa: E402
                                  FALLBACK_CHARACTERS, AssetLibrary)


def run_frames(eng: Engine, seconds: float, dt: float = 0.016,
               surface=None) -> None:
    for _ in range(int(seconds / dt)):
        eng.update(dt)
        assert surface is not None
        eng.draw(surface)


def main() -> int:
    pygame.init()
    eng = Engine(asset_dir=os.path.join(ROOT, "assets"))
    surf = pygame.Surface(eng.size)

    print("== 默认空场 ==")
    assert eng.stage.bg_name == ""            # 不默认使用任何背景素材
    assert eng.stage.sprite_count == 0        # 不默认显示任何立绘
    run_frames(eng, 0.1, surface=surf)        # 空舞台绘制不炸
    print("   无背景/无立绘/空绘制 OK")

    print("== 背景 ==")
    eng.set_background("bg/school", fade=0.0)
    assert eng.stage.bg_name == "bg/school"
    run_frames(eng, 0.1, surface=surf)
    eng.set_background("bg/night", fade=0.3)
    assert eng.stage.bg_transitioning
    run_frames(eng, 0.5, surface=surf)
    assert not eng.stage.bg_transitioning
    assert eng.stage.bg_name == "bg/night"
    print("   背景设置/交叉淡入淡出 OK")

    print("== 立绘显示/淡入 ==")
    spr = eng.show_sprite("akari", image="fg/akari", pos="left", fade=0.5)
    assert spr.alpha == 0.0
    x_left, _ = eng.stage.preset_xy("left")
    assert abs(spr.x - x_left) < 0.01 and abs(spr.y - eng.size[1]) < 0.01
    run_frames(eng, 0.8, surface=surf)
    assert spr.alpha == 255.0, spr.alpha
    print("   淡入完成 OK")

    print("== 自由坐标显示（替换同 id） ==")
    spr2 = eng.show_sprite("akari", image="fg/akari",
                           pos=(eng.size[0] * 0.4, eng.size[1] - 20),
                           fade=0.2)
    assert spr2 is not spr
    assert abs(spr2.x - eng.size[0] * 0.4) < 0.01
    run_frames(eng, 0.4, surface=surf)
    print("   自由坐标 OK")

    print("== 移动补间 ==")
    rx, _ = eng.stage.preset_xy("right")
    eng.move_sprite("akari", to="right", dur=0.6, easing="ease_in_out")
    run_frames(eng, 0.3, surface=surf)
    mid = spr2.x
    assert mid < rx - 50          # 还在路上
    run_frames(eng, 0.6, surface=surf)
    assert abs(spr2.x - rx) < 0.5, spr2.x
    print(f"   移动 {mid:.0f} -> {spr2.x:.0f} OK")

    print("== 透明度控制 ==")
    eng.fade_to("akari", value=100, dur=0.2)
    run_frames(eng, 0.4, surface=surf)
    assert abs(spr2.alpha - 100) < 1.0
    eng.set_alpha("akari", 255)
    assert spr2.alpha == 255.0
    print("   fade_to / set_alpha OK")

    print("== 层级叠放 ==")
    eng.show_sprite("b", image="fg/hinata", pos="center", fade=0.0)
    eng.show_sprite("c", image="fg/sora", pos="right", fade=0.0)
    ids_front_first = eng.stage.sprite_ids()
    assert ids_front_first[0] == "c"            # 后加的在前
    eng.bring_to_front("akari")
    assert eng.stage.sprite_ids()[0] == "akari"
    eng.send_to_back("akari")
    assert eng.stage.sprite_ids()[-1] == "akari"
    eng.layer_up("akari")
    eng.layer_down("akari")
    eng.set_z("c", -50)
    assert eng.stage.sorted_sprites()[0].id == "c"
    eng.bring_to_front("akari")
    run_frames(eng, 0.1, surface=surf)
    print("   front/back/updown/z OK")

    print("== 关闭（淡出后移除） ==")
    eng.hide_sprite("b", fade=0.3)
    run_frames(eng, 0.15, surface=surf)
    assert eng.stage.has_sprite("b")            # 还在淡出
    run_frames(eng, 0.4, surface=surf)
    assert not eng.stage.has_sprite("b")        # 已移除
    eng.remove_sprite("c")
    assert not eng.stage.has_sprite("c")
    print("   hide/remove OK")

    print("== 时间轴序列 ==")
    steps = [
        {"bg": "bg/room", "fade": 0.2},
        {"show": "hero", "img": "fg/akari", "pos": "left", "fade": 0.2},
        {"show": "hero2", "img": "fg/hinata", "pos": "right",
         "fade": 0.2, "z": 10},
        {"parallel": [
            {"move": "hero", "to": "center", "dur": 0.4},
            {"alpha": "hero2", "value": 90, "dur": 0.4},
        ]},
        {"layer": "hero2", "op": "front"},
        {"hide": "hero2", "fade": 0.2},
        {"hide": "hero", "fade": 0.2},
        {"wait": 0.1},
        {"call": lambda: setattr(eng.stage, "bg_name_marker", True)},
    ]
    eng.play(steps)
    assert eng.timeline.state in ("playing",)
    guard = 0
    while eng.timeline.busy and guard < 2000:
        eng.update(0.033)
        eng.draw(surf)
        guard += 1
    assert eng.timeline.state == "done", eng.timeline.state
    assert getattr(eng.stage, "bg_name_marker", False)
    assert not eng.stage.has_sprite("hero")
    assert not eng.stage.has_sprite("hero2")
    assert eng.stage.bg_name == "bg/room"
    print(f"   序列播完（{guard} 帧内）OK")

    print("== 全局暂停 ==")
    eng.show_sprite("p", image="fg/sora", pos="left", fade=0.5)
    p_spr = eng.stage.get_sprite("p")
    eng.pause()
    a0 = p_spr.alpha
    run_frames(eng, 0.5, surface=surf)
    assert p_spr.alpha == a0                    # 冻结
    eng.resume()
    run_frames(eng, 0.8, surface=surf)
    assert p_spr.alpha == 255.0
    eng.remove_sprite("p")
    print("   暂停/继续 OK")

    print("== 资源分类 bg//fg 与目录浏览 ==")
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="kokoro_assets_")
    try:
        tdir = os.path.join(tmp, "assets")
        for sub in ("bg/outdoor", "fg/main"):
            os.makedirs(os.path.join(tdir, *sub.split("/")))
        for rel in ("loose.png",                      # 分类外：GUI 不可见
                    "bg/city.png", "bg/outdoor/park.png",
                    "fg/hero.png", "fg/main/heroine.png"):
            s = pygame.Surface((40, 30))
            s.fill((hash(rel) % 255, 80, 120))
            pygame.image.save(s, os.path.join(tdir, *rel.split("/")))

        lib = AssetLibrary(tdir)
        bgs = lib.all_images("bg")
        fgs = lib.all_images("fg")
        assert bgs == ["bg/city.png".replace(".png", ""),
                       "bg/outdoor/park"] or set(bgs) == {"bg/city",
                                                          "bg/outdoor/park"}
        assert set(bgs) == {"bg/city", "bg/outdoor/park"}
        assert set(fgs) == {"fg/hero", "fg/main/heroine"}
        assert "loose" in lib.all_images()          # 无 kind 时全部可见

        dirs_b, imgs_b = lib.list_dir("bg")
        assert dirs_b == ["outdoor"] and imgs_b == ["bg/city"]
        _, imgs_o = lib.list_dir("bg/outdoor")
        assert imgs_o == ["bg/outdoor/park"]

        # 分类树为空 → 按类兜底伪条目
        empty_dir = os.path.join(tmp, "empty_assets")
        os.makedirs(empty_dir)
        lib_empty = AssetLibrary(empty_dir)
        assert lib_empty.all_images("bg") == list(FALLBACK_BACKGROUNDS)
        assert lib_empty.all_images("fg") == list(FALLBACK_CHARACTERS)

        sx = lib.get("fg/hero")
        th = lib.get_thumbnail("fg/hero", (24, 24))
        assert th.get_width() <= 24 and th.get_height() <= 24
        ph = lib.make_placeholder("任意名", (64, 48), kind="char")
        assert ph.get_size() == (64, 48)
        print(f"   bg={len(bgs)} fg={len(fgs)} 过滤/兜底/缩略图/kind OK")

        # 浏览器子树限制：根下无 up、无法越出分类
        from gui.widgets import ResourceBrowser
        br_rect = pygame.Rect(0, 0, 400, 460)
        browser = ResourceBrowser(br_rect, lib,
                                  lambda target, key: None)
        surf2 = pygame.Surface((800, 600))
        browser.open("bg")
        assert browser.rel_dir == "bg"
        assert ("up", None) not in browser._entries()
        dirs_e, _ = browser.assets.list_dir(browser.rel_dir)
        assert dirs_e == ["outdoor"]
        browser.rel_dir = "bg/outdoor"
        browser.refresh_listing()
        assert ("up", None) in browser._entries()
        browser.draw(surf2)                          # 渲染不炸
        browser.close()
        print("   浏览器定位 bg 根 / 子树限制 / 绘制 OK")

        # 引擎级：嵌套键直接可用；立绘兜底走 fg 子树
        eng2 = Engine(asset_dir=tdir)
        surf3 = pygame.Surface(eng2.size)
        eng2.set_background("bg/outdoor/park", fade=0.0)
        eng2.show_sprite("n", image=None, pos="center", fade=0.2)
        run_frames(eng2, 0.4, surface=surf3)
        assert eng2.stage.has_sprite("n")
        assert eng2.stage.get_sprite("n").name == "fg/hero"   # fg 兜底首个
        print("   引擎级嵌套键 + fg 兜底 OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("== 分辨率预设/画布切换 ==")
    assert eng.size == Engine.DEFAULT_STAGE_SIZE == (1920, 1080)
    rs = eng.show_sprite("rs", image=None, pos="center", fade=0.2)
    run_frames(eng, 0.4, surface=surf)
    rel_x = rs.x / eng.size[0]
    rel_w = rs.surface.get_width() / eng.size[0]
    eng.move_sprite("rs", to="right", dur=5.0)
    tw = next(t for t in eng.tweens.all_tweens()
              if t.obj is rs and t.attr == "x")
    old_to = tw.to_val
    eng.resize_stage((1280, 720))
    assert eng.size == (1280, 720)
    assert abs(tw.to_val - old_to * (720 / 1080)) < 0.01   # 补间目标同步
    assert abs(rs.x / eng.size[0] - rel_x) < 1e-6          # 构图等比保持
    assert abs(rs.surface.get_width() / eng.size[0] - rel_w) < 0.01
    assert tuple(eng.stage._bg_cur.get_size()) == (1280, 720)
    run_frames(eng, 0.3, surface=surf)                     # 新尺寸绘制不炸
    for p in Engine.RESOLUTION_PRESETS:
        eng.resize_stage(p)
        assert eng.size == p
    eng.resize_stage((1920, 1080))
    eng.remove_sprite("rs")
    run_frames(eng, 0.1, surface=surf)
    print("   默认1080p/构图保持/背景重载/补间同步 OK")

    print("== 窗口缩放事件兼容 + 16:9 吸附 ==")
    import main as app
    if sys.platform == "win32":
        # DPI 感知必须在视频初始化前声明，否则桌面尺寸被缩放虚拟化
        assert os.environ.get("SDL_WINDOWS_DPI_AWARENESS") == "permonitorv2"
    e_win = pygame.event.Event(pygame.WINDOWRESIZED, x=800, y=600)
    e_vid = pygame.event.Event(pygame.VIDEORESIZE, w=800, h=600)
    assert app.resize_event_size(e_win) == (800, 600)   # WINDOWRESIZED: x/y
    assert app.resize_event_size(e_vid) == (800, 600)   # VIDEORESIZE: w/h
    for w0, h0 in ((1656, 728), (1400, 900), (1920, 1080)):
        pr, dr = app.compute_layout(w0, h0, eng.size)
        ratio = dr.w / dr.h
        assert abs(ratio - eng.size[0] / eng.size[1]) < 0.02
        assert dr.right <= pr.x                    # 贴边：右缘紧邻面板
        assert dr.left == 0 and dr.top == 0        # 上/左零黑边
        assert dr.bottom <= h0 - app.ui_s(32)      # 不压状态栏
    # 拖拽吸附：始终回到 16:9，且不低于最小窗口
    assert app.snap_16_9(1200, 600) == (1200, 675)      # 保宽调高更近
    assert app.snap_16_9(1100, 700) == (1100, 619)      # 保宽调高更近
    assert app.snap_16_9(100, 100) == (960, 540)        # 最小钳制（16:9）
    assert app.snap_16_9(2560, 1400) == (2560, 1440)
    assert app.choose_startup_preset(1366, 768) == (1280, 720)
    assert app.choose_startup_preset(1920, 1080) == (1920, 1080)
    assert app.choose_startup_preset(3840, 2160) == (2560, 1440)
    print("   双事件属性/布局等比/snap_16_9/启动降级 OK")

    print("== 面板分辨率切换链路 ==")
    from gui.panel import ControlPanel
    applied = []
    p_rect = pygame.Rect(1200, 20, 432, 900)
    pnl = ControlPanel(eng, p_rect,
                       on_preset_change=lambda p: applied.append(p),
                       desktop_size=(1920, 1080))
    assert len(pnl.res_options) == 4
    assert pnl.cyc_res.value == "1920×1080"
    # 选中超屏预设 → 应用按钮置灰
    pnl.pending_resolution = "2560×1440"
    pnl._sync_resolution_ui()
    assert not pnl.btn_apply_res.enabled
    # 选中可用预设 → 点击应用触发回调
    pnl.pending_resolution = "1280×720"
    pnl._sync_resolution_ui()
    assert pnl.btn_apply_res.enabled
    pnl.btn_apply_res.callback()
    assert applied == [(1280, 720)]
    # 当前已是目标档 → 按钮置灰
    pnl.pending_resolution = "1280×720"
    eng.resize_stage((1280, 720))
    pnl._sync_resolution_ui()
    assert not pnl.btn_apply_res.enabled
    eng.resize_stage((1920, 1080))
    run_frames(eng, 0.1, surface=surf)
    print("   Cycler/应用回调/超屏与同档置灰 OK")

    print("== GUI DPI 缩放 + 面板滚动 ==")
    from gui import widgets as W
    W.set_ui_scale(1.0)
    base_h = W.get_font(14).get_height()
    assert W.s(100) == 100 and W.UI_SCALE == 1.0
    pnl_base = ControlPanel(eng, p_rect, desktop_size=(1920, 1080))
    base_bottom = pnl_base.content_bottom - pnl_base.rect.y

    W.set_ui_scale(1.5)                      # 模拟 150% Windows 缩放
    assert W.s(100) == 150 and W.s(-3) >= 1
    scaled_h = W.get_font(14).get_height()
    assert abs(scaled_h / base_h - 1.5) < 0.25   # 字体像素随 DPI 放大
    pnl_scaled = ControlPanel(eng, p_rect, desktop_size=(1920, 1080))
    scaled_bottom = pnl_scaled.content_bottom - pnl_scaled.rect.y
    assert abs(scaled_bottom / base_bottom - 1.5) < 0.15  # 行距等比放大
    # 内容超出 → 滚动激活；滚轮生效；事件坐标平移正确
    assert pnl_scaled.max_scroll() > 0
    y0 = pnl_scaled.scroll_y
    pnl_scaled.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=5, pos=(1300, 400)))
    assert pnl_scaled.scroll_y > y0
    ev = pnl_scaled._translate_event(pygame.event.Event(
        pygame.MOUSEMOTION, pos=(1300, 500)))
    assert ev.pos[1] == 500 - pnl_scaled.scroll_y
    # 低矮面板（模拟低分辨率）同样可滚，绘制不炸
    pnl_low = ControlPanel(eng, pygame.Rect(1200, 20, 432, 260),
                           desktop_size=(1366, 768))
    assert pnl_low.max_scroll() > 0
    pnl_low.draw(surf)
    pnl_scaled.draw(surf)
    W.set_ui_scale(1.0)                      # 还原基准，后续测试不受影响
    W.get_font(14)
    print("   字体/行距缩放、滚动、事件平移、还原 OK")

    print("== 立绘距离缩放 + 越界移动 ==")
    dspr = eng.show_sprite("dist", image=None, pos="center", fade=0.3)
    run_frames(eng, 0.5, surface=surf)
    w0, h0 = dspr.width, dspr.height
    cx0, by0 = dspr.x, dspr.y
    eng.set_sprite_scale("dist", 0.5)
    assert abs(dspr.scale - 0.5) < 1e-6
    assert abs(dspr.width - w0 * 0.5) <= 2
    assert abs(dspr.x - cx0) < 1.0            # 水平中心锚点不变
    assert abs(dspr.y - by0) < 1.0            # 脚线锚点不变
    eng.set_sprite_scale("dist", 1.25)
    assert dspr.width > w0
    eng.set_sprite_scale("dist", 1.0)
    assert abs(dspr.width - w0) <= 1 and abs(dspr.height - h0) <= 1
    rel_w = dspr.width / eng.size[0]
    eng.resize_stage((1280, 720))
    assert abs(dspr.width / eng.size[0] - rel_w) < 0.02  # base 同步缩放
    eng.resize_stage((1920, 1080))

    from gui.panel import ControlPanel as CP2
    pnl2 = ControlPanel(eng, pygame.Rect(1200, 20, 432, 900),
                        desktop_size=(1920, 1080))
    assert pnl2.sld_x.min_val == -1920 and pnl2.sld_x.max_val == 3840
    pnl2.select_sprite("dist")
    pnl2.sld_x.set_value(-500.0, fire=True)
    assert abs(dspr.x - (-500.0)) < 1e-6      # 可完全移出左边界
    eng.resize_stage((1280, 720))
    pnl2.update(0.016)
    assert pnl2.sld_x.max_val == 2560 and pnl2.sld_y.min_val == -720
    eng.resize_stage((1920, 1080))
    pnl2.update(0.016)

    assert len(pnl2.cyc_dist.options) == 5
    pnl2.select_sprite("dist")
    pnl2.cyc_dist.index = 4
    pnl2._on_dist_level(pnl2.cyc_dist.value)               # 特写 1.75x
    assert abs(eng.get_sprite_scale("dist") - 1.75) < 1e-6
    assert abs(pnl2.pending_scale - 1.75) < 1e-6
    pnl2.show_img = "fg/hinata"
    pnl2._on_show()                            # 新立绘继承当前距离档
    new_id = pnl2.sel_sid
    assert new_id != "dist"
    assert abs(eng.get_sprite_scale(new_id) - 1.75) < 1e-6
    # 切回标准档即时生效（标准=1.25）
    pnl2.cyc_dist.index = 2
    pnl2._on_dist_level(pnl2.cyc_dist.value)
    assert abs(eng.get_sprite_scale(new_id) - 1.25) < 1e-6
    eng.remove_sprite(new_id)
    eng.remove_sprite("dist")
    run_frames(eng, 0.1, surface=surf)
    print("   五档缩放/锚点保持/base同步/越界坐标/面板链路 OK")

    print("== 舞台鼠标拖拽立绘 ==")
    import main as app
    disp_r = pygame.Rect(100, 100, 960, 540)      # 假想显示区（960x540 视口）
    dsize = eng.size
    dspr = eng.show_sprite("dragt", image=None, pos=(600, 700), fade=0.0)
    ctl = app.StageDragController(eng, pnl2)

    def to_screen(cx, cy):
        return (disp_r.x + cx / dsize[0] * disp_r.w,
                disp_r.y + cy / dsize[1] * disp_r.h)

    # 制造活动补间：begin 应选中并取消补间，且无跳变
    # （按下点取脚线上方一点：矩形碰撞不含底边线）
    eng.move_sprite("dragt", to="right", dur=5.0)
    assert ctl.begin(disp_r, *to_screen(600, 690)) is True
    assert pnl2.sel_sid == "dragt"
    assert not eng.tweens.has_tween(dspr, "x")
    assert abs(dspr.x - 600) < 1e-6 and abs(dspr.y - 700) < 1e-6
    # 锚点正上方抓取（偏移 y=+10）：拖动严格跟随光标画布坐标
    ctl.motion(disp_r, *to_screen(650, 650))
    assert abs(dspr.x - 650) < 1e-6
    assert abs(dspr.y - 660) < 1e-6
    # 非锚点抓取：保持抓取偏移
    ctl.end()
    dspr.x, dspr.y = 600.0, 700.0
    assert ctl.begin(disp_r, *to_screen(650, 680)) is True
    offx, offy = dspr.x - 650, dspr.y - 680       # (-50, +20)
    ctl.motion(disp_r, *to_screen(300, 400))
    assert abs(dspr.x - (300 + offx)) < 1e-6
    assert abs(dspr.y - (400 + offy)) < 1e-6
    # 可拖出画布边界（负坐标不钳制）
    ctl.motion(disp_r, *to_screen(-800, -900))
    assert abs(dspr.x - (-800 + offx)) < 1e-6
    assert abs(dspr.y - (-900 + offy)) < 1e-6
    # end 之后不再移动
    ctl.end()
    last_x = dspr.x
    ctl.motion(disp_r, *to_screen(500, 500))
    assert abs(dspr.x - last_x) < 1e-6
    # 空处按下：取消选中且不进入拖拽
    assert ctl.begin(disp_r, *to_screen(30, 30)) is False
    assert pnl2.sel_sid is None and not ctl.active
    eng.remove_sprite("dragt")
    run_frames(eng, 0.1, surface=surf)
    print("   抓取偏移/补间接管/越界拖动/结束失效/空处取消 OK")

    print("== move 单轴/双轴语义 ==")
    mspr = eng.show_sprite("mv", image=None, pos=(900, 400), fade=0.0)
    left_x, _ = eng.stage.preset_xy("left")
    # 水平预设：只动 X，Y 恒定且完全不创建 Y 补间
    eng.move_sprite("mv", to="left", dur=0.4)
    assert not eng.tweens.has_tween(mspr, "y")
    run_frames(eng, 0.6, surface=surf)
    assert abs(mspr.x - left_x) < 0.5
    assert abs(mspr.y - 400) < 1e-6
    # 显式二维目标：双轴同时补间并各自到位
    eng.move_sprite("mv", to=(1300, 800), dur=0.3)
    assert eng.tweens.has_tween(mspr, "x")
    assert eng.tweens.has_tween(mspr, "y")
    run_frames(eng, 0.5, surface=surf)
    assert abs(mspr.x - 1300) < 0.5 and abs(mspr.y - 800) < 0.5
    # 单轴移动不打断另一轴进行中的补间（并行合成）
    eng.move_sprite("mv", to=(1400, 500), dur=2.0)
    run_frames(eng, 0.2, surface=surf)
    eng.move_sprite("mv", to="left", dur=0.3)
    assert eng.tweens.has_tween(mspr, "x")
    assert eng.tweens.has_tween(mspr, "y")          # 原 Y 补间仍存活
    run_frames(eng, 2.5, surface=surf)
    assert abs(mspr.x - left_x) < 0.5
    assert abs(mspr.y - 500) < 0.5                  # Y 未被重置、最终到位
    # Timeline 层端到端：to="right" 仅 X 变化
    eng.play([
        {"show": "mvt", "pos": (900, 350), "fade": 0.0},
        {"move": "mvt", "to": "right", "dur": 0.2},
    ])
    guard = 0
    while eng.timeline.busy and guard < 600:
        eng.update(0.033)
        eng.draw(surf)
        guard += 1
    mvt = eng.stage.get_sprite("mvt")
    assert abs(mvt.x - dsize[0] * 0.75) < 0.5
    assert abs(mvt.y - 350) < 1e-6
    eng.remove_sprite("mv")
    eng.remove_sprite("mvt")
    run_frames(eng, 0.1, surface=surf)
    print("   水平只动X/Y恒定/元组双轴/并行合成/timeline端到端 OK")

    print("== 窗口自适应工作区（零黑边反解） ==")
    R = 16 / 9
    # 零 GUI 占用：恒等情形
    assert app.fit_window_to_work(1920, 1080, 2560, 1440) == (1920, 1080)
    # 带 GUI 占用：舞台区域比例 == 16:9 且窗口 ≤ 工作区余量
    gw, gh = app._gui_chrome()
    W, H = app.fit_window_to_work(2560, 1440, 2560, 1440, gw, gh)
    assert W <= 2560 - app.CHROME_PAD_W and H <= 1440 - app.CHROME_TITLE_H
    assert abs((W - gw) / (H - gh) - R) < 0.01
    # 换一组画布/工作区同样满足反解关系
    for cv in ((1280, 720), (1920, 1080), (2560, 1440)):
        W2, H2 = app.fit_window_to_work(*cv, 1920, 1080, gw, gh)
        assert W2 <= 1920 - app.CHROME_PAD_W
        assert H2 <= 1080 - app.CHROME_TITLE_H
        assert abs((W2 - gw) / (H2 - gh) - R) < 0.02
    # 极端小工作区：钳制到最小窗口（16:9）
    assert app.fit_window_to_work(1280, 720, 500, 400, gw, gh) == (960, 540)
    # 启动选档逻辑保持不变（画布档位语义）
    assert app.choose_startup_preset(2560, 1440) == (2560, 1440)
    # 贴边布局：画布零边距，右缘紧邻面板；宽度约束时贴顶
    pr3, dr3 = app.compute_layout(2448, 1047, (1920, 1080))
    assert dr3.left >= 0 and dr3.top >= 0
    assert dr3.right <= pr3.left and dr3.bottom <= 1047 - app.ui_s(32)
    # 宽度约束场景：垂直贴顶 + 水平居中（无顶部黑条）
    pr4, dr4 = app.compute_layout(2448, 700, (1920, 1080))
    assert dr4.top == 0 and dr4.left > 0
    # 高度约束场景：水平居中留白属预期（对称）
    assert abs(dr3.centery - (1047 - app.ui_s(32)) // 2) <= 1
    # fit 反解的理想窗口：画布原生分辨率 1:1 满铺、零黑边
    fw0, fh0 = app.fit_window_to_work(1920, 1080, 2560, 1440,
                                      app._gui_chrome()[0],
                                      app._gui_chrome()[1])
    pr5, dr5 = app.compute_layout(fw0, fh0, (1920, 1080))
    assert dr5.size == (1920, 1080) and dr5.topleft == (0, 0)
    # 程序化尺寸（±1px）不触发吸附回弹；用户拖拽尺寸正常吸附
    assert not app.resize_needs_snap((1722, 969), (1722, 969))
    assert not app.resize_needs_snap((1721, 968), (1722, 969))
    assert app.resize_needs_snap((2000, 1125), (1722, 969))
    assert app.resize_needs_snap((2000, 1125), None)
    print("   反解比例/约束钳制/贴边布局/吸附豁免/选档不变 OK")

    print("== 固定步长补帧 + 渲染缓存 ==")
    from kokoro_engine.renderer import StageRenderer
    # 累加器：两个半步恰好合成一个逻辑步，alpha 归零
    eng._acc = 0.0
    a1 = eng.advance(1 / 120)
    assert 0.4 < a1 < 0.6, a1                   # 半步 → 因子≈0.5
    a2 = eng.advance(1 / 120)
    assert a2 == 0.0, a2                        # 跨过整步后归零
    # 插值位置：update 快照 prev，render_pos 介于 prev 与 cur 之间
    isp = eng.show_sprite("itp", image=None, pos=(600, 700), fade=0.0)
    eng.move_sprite("itp", to=(1400, 900), dur=1.0)
    eng.update(1 / 60)
    px, py = isp.prev_x, isp.prev_y
    assert abs(px - 600) < 1e-6 and abs(py - 700) < 1e-6
    assert px <= isp.x <= px + (1400 - 600) / 60 + 1e-6
    rx, ry = isp.render_pos(0.5)
    assert px - 1e-6 <= rx <= isp.x + 1e-6
    # snap 路径：手动位移后插值基准立即贴合
    isp.x, isp.y = 300.0, 300.0
    isp.snap_render()
    rp = isp.render_pos(0.37)
    assert abs(rp[0] - 300.0) < 1e-9 and abs(rp[1] - 300.0) < 1e-9
    # 暂停冻结：advance 不推进、返回 1.0、位置静止
    x_before = isp.x
    eng.pause()
    assert eng.advance(1 / 30) == 1.0
    assert abs(isp.x - x_before) < 1e-12
    eng.resume()
    eng.remove_sprite("itp")
    # 渲染器：缓存命中 + 插值绘制不炸
    rnd = StageRenderer(eng)
    rsurf = pygame.Surface((1280, 720))
    cspr = eng.show_sprite("rc", image=None, pos="center", fade=0.0)
    rrect = pygame.Rect(0, 0, 1280, 720)
    rnd.draw(rsurf, rrect, 0.5)
    assert cspr._disp_cache is not None          # 立绘缩放缓存已建
    n_bg = len(rnd._bg_cache)
    rnd.draw(rsurf, rrect, 0.7)                  # 同尺寸再次绘制
    assert len(rnd._bg_cache) == n_bg            # 命中缓存未增长
    eng.remove_sprite("rc")
    run_frames(eng, 0.1, surface=surf)
    print("   累加器/插值区间/snap贴合/暂停冻结/渲染缓存 OK")

    print("== 渲染一致性 / 无陈旧缓存 ==")
    from kokoro_engine.renderer import StageRenderer as SR2

    def _bytes(s):
        return pygame.image.tobytes(s, "RGBA")

    cmp_spr = eng.show_sprite("cmp", image=None, pos="center", fade=0.0)
    # 1:1 尺寸：renderer 输出必须与 stage.draw 逐像素一致
    ref = pygame.Surface(eng.size)
    eng.stage.draw(ref)
    got = pygame.Surface(eng.size)
    SR2(eng).draw(got, pygame.Rect(0, 0, *eng.size), 1.0)
    assert _bytes(ref) == _bytes(got), "1:1 渲染不一致"
    # 连续切换背景多轮：旧渲染器输出与全新渲染器逐像素一致
    scene = pygame.Surface((960, 540))
    r_a = SR2(eng)
    rect_s = pygame.Rect(0, 0, 960, 540)
    for name in ("bg/school", "bg/night", "bg/school", "bg/room"):
        eng.set_background(name, fade=0.0)
        r_a.draw(scene, rect_s, 1.0)
        chk = pygame.Surface((960, 540))
        SR2(eng).draw(chk, rect_s, 1.0)
        assert _bytes(scene) == _bytes(chk), f"陈旧缓存: {name}"
    eng.remove_sprite("cmp")
    print("   1:1逐像素一致/多轮切背景无陈旧缓存 OK")

    state = eng.get_state()
    assert isinstance(state, dict) and "sprites" in state
    print("== 全部通过 PASS ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
