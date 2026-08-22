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
    e_win = pygame.event.Event(pygame.WINDOWRESIZED, x=800, y=600)
    e_vid = pygame.event.Event(pygame.VIDEORESIZE, w=800, h=600)
    assert app.resize_event_size(e_win) == (800, 600)   # WINDOWRESIZED: x/y
    assert app.resize_event_size(e_vid) == (800, 600)   # VIDEORESIZE: w/h
    for w0, h0 in ((1656, 728), (1400, 900), (1920, 1080)):
        pr, dr = app.compute_layout(w0, h0, eng.size)
        ratio = dr.w / dr.h
        assert abs(ratio - eng.size[0] / eng.size[1]) < 0.02
        assert dr.right <= pr.x - 8
        assert dr.top >= app.MARGIN and dr.bottom <= h0 - app.STATUS_BAR_H
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

    state = eng.get_state()
    assert isinstance(state, dict) and "sprites" in state
    print("== 全部通过 PASS ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
