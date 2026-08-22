"""无头冒烟测试：用 SDL dummy 驱动跑通引擎全部 API。

运行：python tests/smoke_test.py
"""

from __future__ import annotations

import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from kokoro_engine import Engine  # noqa: E402


def run_frames(eng: Engine, seconds: float, dt: float = 0.016,
               surface=None) -> None:
    n = int(seconds / dt)
    for _ in range(n):
        eng.update(dt)
        assert surface is not None
        eng.draw(surface)


def main() -> int:
    pygame.init()
    eng = Engine(asset_dir="assets")
    surf = pygame.Surface(eng.size)

    print("== 背景 ==")
    eng.set_background("bg_school", fade=0.0)
    assert eng.stage.bg_name == "bg_school"
    run_frames(eng, 0.1, surface=surf)
    eng.set_background("bg_night", fade=0.3)
    assert eng.stage.bg_transitioning
    run_frames(eng, 0.5, surface=surf)
    assert not eng.stage.bg_transitioning
    assert eng.stage.bg_name == "bg_night"
    print("   背景设置/交叉淡入淡出 OK")

    print("== 立绘显示/淡入 ==")
    spr = eng.show_sprite("akari", image="char_akari", pos="left",
                          fade=0.5)
    assert spr.alpha == 0.0
    x_left, _ = eng.stage.preset_xy("left")
    assert abs(spr.x - x_left) < 0.01 and abs(spr.y - eng.size[1]) < 0.01
    run_frames(eng, 0.8, surface=surf)
    assert spr.alpha == 255.0, spr.alpha
    print("   淡入完成 OK")

    print("== 自由坐标显示（替换同 id） ==")
    spr2 = eng.show_sprite("akari", image="char_akari",
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
    b = eng.show_sprite("b", image="char_hinata", pos="center", fade=0.0)
    c = eng.show_sprite("c", image="char_sora", pos="right", fade=0.0)
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
        {"bg": "bg_room", "fade": 0.2},
        {"show": "hero", "img": "char_akari", "pos": "left", "fade": 0.2},
        {"show": "hero2", "img": "char_hinata", "pos": "right",
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
    assert eng.stage.bg_name == "bg_room"
    print(f"   序列播完（{guard} 帧内）OK")

    print("== 全局暂停 ==")
    eng.show_sprite("p", image="char_sora", pos="left", fade=0.5)
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

    state = eng.get_state()
    assert isinstance(state, dict) and "sprites" in state
    print("== 全部通过 PASS ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
