"""kokoro_engine 引擎门面：对外唯一的演出 API。

典型用法：
    eng = Engine()
    eng.set_background("bg_school", fade=1.0)
    eng.show_sprite("akari", image="char_akari", pos="left", fade=0.8)
    eng.move_sprite("akari", to="right", dur=2.0)
    eng.play([...])          # 或逐条调用上述 API
    while running:
        eng.update(dt); eng.draw(stage_surface)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union

import pygame

from .assets import AssetLibrary
from .sprite import Sprite
from .stage import Stage
from .timeline import TimelinePlayer
from .tween import TweenManager

PosLike = Union[str, Tuple[float, float], List[float]]


class Engine:
    DEFAULT_STAGE_SIZE = (1152, 648)   # 16:9
    CHAR_MAX_H_FRAC = 0.92             # 立绘最大高度占舞台高度比例
    CHAR_PLACEHOLDER_ASPECT = 0.52     # 占位立绘宽高比

    def __init__(self, stage_size: Tuple[int, int] = DEFAULT_STAGE_SIZE,
                 asset_dir: str = "assets") -> None:
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()
        self.assets = AssetLibrary(asset_dir)
        self.tweens = TweenManager()
        self.stage = Stage(stage_size, self.tweens)
        self.timeline = TimelinePlayer()
        self.timeline.engine = self
        self.paused = False            # 全局暂停：冻结所有动画与时间轴

    # -------------------------------------------------------------- 内部工具
    @property
    def size(self) -> Tuple[int, int]:
        return self.stage.size

    def _resolve_pos(self, pos: PosLike) -> Tuple[float, float]:
        """预设位名称 / (x, y) 均可；y 为立绘脚线。"""
        if isinstance(pos, str):
            return self.stage.preset_xy(pos)
        x, y = float(pos[0]), float(pos[1])
        return x, y

    def _char_surface(self, image: Optional[str]) -> pygame.Surface:
        """加载立绘图并按舞台高度适配（等比，不放大只缩小）。"""
        max_h = int(self.size[1] * self.CHAR_MAX_H_FRAC)
        if image is None:
            names = self.assets.characters()
            image = names[0]
        if not self.assets.has_file(image):
            ph = max_h
            pw = int(ph * self.CHAR_PLACEHOLDER_ASPECT)
            return self.assets.get(image, size=(pw, ph))
        native = self.assets.get(image)
        scale = min(1.0, max_h / native.get_height())
        w = max(1, int(native.get_width() * scale))
        h = max(1, int(native.get_height() * scale))
        if native.get_size() != (w, h):
            return pygame.transform.smoothscale(native, (w, h))
        return native.copy()

    # ------------------------------------------------------------------ 背景
    def set_background(self, name: str, fade: float = 0.5,
                       easing: str = "ease_in_out") -> None:
        surf = self.assets.get(name, size=self.size)
        self.stage.set_background(surf, name, fade=fade, easing=easing)

    # ------------------------------------------------------------------ 立绘
    def show_sprite(self, sid: str, image: Optional[str] = None,
                    pos: PosLike = "center", fade: float = 0.6,
                    z: Optional[float] = None,
                    alpha_from: Optional[float] = None,
                    easing: str = "linear") -> Sprite:
        """显示立绘。fade>0 时从透明淡入；同 id 已存在则替换重建。"""
        if self.stage.has_sprite(sid):
            self.remove_sprite(sid)

        xy = self._resolve_pos(pos)
        surf = self._char_surface(image)
        if z is None:
            z = self.stage.max_z() + 10.0 if self.stage.sprite_count else 0.0
        spr = self.stage.add_sprite(sid, surf, xy[0], xy[1], z=z)
        img_name = image if image is not None else \
            (self.assets.characters()[0] if self.assets.characters() else sid)
        spr.name = img_name

        start_alpha = alpha_from if alpha_from is not None else (0.0 if fade > 0 else 255.0)
        if fade > 0:
            spr.alpha = max(0.0, min(255.0, start_alpha))
            self.tweens.tween_attr(spr, "alpha", 255.0, fade, easing)
        else:
            spr.alpha = 255.0
        return spr

    def hide_sprite(self, sid: str, fade: float = 0.6,
                    easing: str = "linear") -> None:
        """淡出并移除；fade<=0 时立即移除。"""
        spr = self.stage.get_sprite(sid)
        if spr is None:
            return
        if fade <= 0:
            self.remove_sprite(sid)
            return

        def _remove() -> None:
            self.remove_sprite(sid)

        self.tweens.tween_attr(spr, "alpha", 0.0, fade, easing, _remove)

    def remove_sprite(self, sid: str) -> None:
        spr = self.stage.get_sprite(sid)
        if spr is not None:
            self.tweens.kill(spr)
            self.stage.remove_sprite(sid)

    def move_sprite(self, sid: str, to: PosLike = "center",
                    dur: float = 1.0, easing: str = "ease_in_out") -> None:
        spr = self.stage.require_sprite(sid)
        xy = self._resolve_pos(to)
        self.tweens.kill(spr, "x")
        self.tweens.kill(spr, "y")
        self.tweens.tween_xy(spr, xy, dur, easing)

    def fade_to(self, sid: str, value: float, dur: float = 0.5,
                easing: str = "linear") -> None:
        """把立绘透明度补间到 value (0~255)。"""
        spr = self.stage.require_sprite(sid)
        value = max(0.0, min(255.0, float(value)))
        self.tweens.tween_attr(spr, "alpha", value, dur, easing)

    def set_alpha(self, sid: str, value: float) -> None:
        spr = self.stage.require_sprite(sid)
        self.tweens.kill(spr, "alpha")
        spr.alpha = max(0.0, min(255.0, float(value)))

    # ------------------------------------------------------------------ 层级
    def set_z(self, sid: str, z: float) -> None:
        self.stage.set_z(sid, z)

    def bring_to_front(self, sid: str) -> None:
        self.stage.bring_to_front(sid)

    def send_to_back(self, sid: str) -> None:
        self.stage.send_to_back(sid)

    def layer_up(self, sid: str) -> None:
        self.stage.nudge_layer(sid, +1)

    def layer_down(self, sid: str) -> None:
        self.stage.nudge_layer(sid, -1)

    # ------------------------------------------------------------------ 时间轴
    def play(self, steps: List[Dict], engine=None) -> None:
        self.timeline.play(steps, engine=self)

    def stop_timeline(self) -> None:
        self.timeline.stop()

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused

    # ------------------------------------------------------------------ 主循环
    def update(self, dt: float) -> None:
        if self.paused:
            return
        self.tweens.update(dt)
        self.timeline.update(dt)

    def draw(self, target: pygame.Surface) -> None:
        self.stage.draw(target)

    # ------------------------------------------------------------------ 状态
    def get_state(self) -> Dict:
        sprites = []
        for spr in reversed(self.stage.sorted_sprites()):   # 前→后
            sprites.append({
                "id": spr.id,
                "img": spr.name,
                "z": spr.z,
                "alpha": round(spr.alpha),
                "x": round(spr.x),
                "y": round(spr.y),
                "moving": self.tweens.has_tween(spr, "x"),
            })
        return {
            "stage_size": self.size,
            "bg": self.stage.bg_name,
            "bg_transitioning": self.stage.bg_transitioning,
            "sprites": sprites,
            "timeline_state": self.timeline.state,
            "timeline_progress": self.timeline.progress_text,
            "paused": self.paused,
        }
