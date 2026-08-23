"""舞台：背景管理 + 立绘集合的增删、层级与绘制。"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pygame

from .sprite import Sprite
from .tween import Tween

# 预设位：水平位置占舞台宽度的比例
PRESET_X_FRAC: Dict[str, float] = {
    "left": 0.25,
    "center": 0.50,
    "right": 0.75,
}

# 预设位作用的轴：水平预设只动 X，垂直预设只动 Y（预留 top/bottom）
PRESET_AXIS: Dict[str, str] = {
    "left": "x",
    "center": "x",
    "right": "x",
}

# 舞台清屏底色（无背景时的空场颜色）
STAGE_CLEAR = (12, 12, 16)


class Stage:
    def __init__(self, size: Tuple[int, int], tweens) -> None:
        self.size = size
        self.w, self.h = size
        self.tweens = tweens          # 引擎级补间管理器（统一受暂停控制）
        # 背景状态（交叉淡入淡出）
        self._bg_cur: Optional[pygame.Surface] = None
        self._bg_prev: Optional[pygame.Surface] = None
        self._bg_progress = 1.0       # 1 表示无切换进行中
        self.bg_name = ""
        self.bg_transitioning = False
        # 背景内容版本号：任何背景表面更替时自增，
        # 供渲染器安全地作废缩放缓存（避免 id() 复用歧义）。
        self.bg_version = 0
        # 立绘
        self._sprites: Dict[str, Sprite] = {}
        self._seq_counter = 0

    # ------------------------------------------------------------------ 坐标
    def preset_xy(self, preset: str) -> Tuple[float, float]:
        frac = PRESET_X_FRAC.get(preset)
        if frac is None:
            raise ValueError(f"未知预设位: {preset}")
        return self.w * frac, float(self.h)

    def resolve_axis_target(self, to):
        """把移动目标解析为单轴或双轴语义（供 move 类补间使用）。

        返回：
        - ("x", 目标x)   —— 水平预设 left/center/right，只动 X；
        - ("y", 目标y)   —— 垂直预设（预留 top/bottom），只动 Y；
        - ("xy", (x,y))  —— 显式二维目标，双轴同时补间。
        """
        if isinstance(to, str):
            axis = PRESET_AXIS.get(to)
            if axis == "x":
                return "x", self.w * PRESET_X_FRAC[to]
            if axis == "y":
                raise ValueError(f"垂直预设尚未定义: {to}")
            raise ValueError(f"未知预设位: {to}")
        try:
            x, y = float(to[0]), float(to[1])
        except (TypeError, ValueError, IndexError) as exc:
            raise ValueError(f"移动目标格式错误: {to!r}") from exc
        return "xy", (x, y)

    # ------------------------------------------------------------------ 背景
    def set_background(self, surface: pygame.Surface, name: str,
                       fade: float = 0.5, easing: str = "ease_in_out") -> None:
        surface = surface.copy()
        if surface.get_size() != self.size:
            surface = pygame.transform.smoothscale(surface, self.size)

        if fade <= 0 or self._bg_cur is None:
            self._bg_prev = None
            self._bg_cur = surface
            self._bg_progress = 1.0
            self.bg_transitioning = False
            self.bg_name = name
            self.bg_version += 1
            return

        self.tweens.kill(self, "_bg_progress")
        self._bg_prev = self._bg_cur
        self._bg_cur = surface
        self.bg_name = name
        self.bg_transitioning = True
        self._bg_progress = 0.0
        self.bg_version += 1

        def done() -> None:
            self._bg_prev = None
            self.bg_transitioning = False
            self._bg_progress = 1.0

        self.tweens.add(Tween(self, "_bg_progress", 0.0, 1.0, fade,
                              easing, done))

    # ------------------------------------------------------------------ 立绘
    def add_sprite(self, sid: str, surface: pygame.Surface, x: float, y: float,
                   z: float = 0.0) -> Sprite:
        if sid in self._sprites:
            raise KeyError(f"立绘 id 已存在: {sid}")
        spr = Sprite(sid, surface, x, y, z=z, seq=self._seq_counter)
        self._seq_counter += 1
        self._sprites[sid] = spr
        return spr

    def get_sprite(self, sid: str) -> Optional[Sprite]:
        return self._sprites.get(sid)

    def has_sprite(self, sid: str) -> bool:
        return sid in self._sprites

    @property
    def sprite_count(self) -> int:
        return len(self._sprites)

    def max_z(self) -> float:
        return max(s.z for s in self._sprites.values()) if self._sprites else 0.0

    def min_z(self) -> float:
        return min(s.z for s in self._sprites.values()) if self._sprites else 0.0

    def require_sprite(self, sid: str) -> Sprite:
        spr = self._sprites.get(sid)
        if spr is None:
            raise KeyError(f"立绘不存在: {sid}")
        return spr

    def remove_sprite(self, sid: str) -> None:
        self._sprites.pop(sid, None)

    def sprite_ids(self) -> List[str]:
        """按从前到后的显示顺序返回 id。"""
        return [s.id for s in self.sorted_sprites()][::-1]

    def sorted_sprites(self) -> List[Sprite]:
        """按渲染顺序（远→近）排序。"""
        return sorted(self._sprites.values(), key=lambda s: (s.z, s.seq))

    # 层级操作
    def set_z(self, sid: str, z: float) -> None:
        self.require_sprite(sid).z = float(z)

    def bring_to_front(self, sid: str) -> None:
        if self.has_sprite(sid):
            self.set_z(sid, self.max_z() + 10)

    def send_to_back(self, sid: str) -> None:
        if self.has_sprite(sid):
            self.set_z(sid, self.min_z() - 10)

    def nudge_layer(self, sid: str, delta: int) -> None:
        zs = sorted({s.z for s in self._sprites.values()})
        cur = self.require_sprite(sid).z
        if delta > 0:
            higher = [z for z in zs if z > cur]
            self.set_z(sid, higher[0] if higher else zs[-1])
        elif delta < 0:
            lower = [z for z in zs if z < cur]
            self.set_z(sid, lower[-1] if lower else zs[0])

    # ------------------------------------------------------------------ 画布
    def resize(self, new_size: Tuple[int, int],
               bg_surface_loader=None) -> None:
        """逻辑画布等比切换（16:9）。

        - 立绘位置与贴图按同一系数缩放，场景构图比例严格保持；
        - 通过 bg_surface_loader(name, size) 重载当前背景；
        - 进行中的背景过渡立即结束。
        """
        new_size = (int(new_size[0]), int(new_size[1]))
        new_w, new_h = new_size
        if new_w == self.w and new_h == self.h:
            return
        s = new_w / self.w                      # 16:9 → x/y 同比
        for spr in self._sprites.values():
            spr.x *= s
            spr.y *= s
            # 距离缩放的采样基准同步缩放，保持 set_scale 相对倍率不变
            bw = max(1, int(spr.base_surface.get_width() * s + 0.5))
            bh = max(1, int(spr.base_surface.get_height() * s + 0.5))
            if (bw, bh) != spr.base_surface.get_size():
                try:
                    spr.base_surface = pygame.transform.smoothscale(
                        spr.base_surface, (bw, bh))
                except (pygame.error, ValueError):
                    pass
            w = max(1, int(spr.surface.get_width() * s + 0.5))
            h = max(1, int(spr.surface.get_height() * s + 0.5))
            if (w, h) != spr.surface.get_size():
                try:
                    spr.surface = pygame.transform.smoothscale(
                        spr.surface, (w, h))
                except (pygame.error, ValueError):
                    pass
        self.size = (new_w, new_h)
        self.w, self.h = new_w, new_h
        if bg_surface_loader is not None and self.bg_name:
            try:
                self._bg_cur = bg_surface_loader(self.bg_name, self.size)
                self.bg_version += 1
            except Exception as exc:
                print(f"[stage] 背景重载失败({exc})，保留原背景。")
        # 过渡立即结束
        self._bg_prev = None
        self.bg_transitioning = False
        self._bg_progress = 1.0

    # ------------------------------------------------------------------ 绘制
    def background_layers(self) -> List[Tuple[pygame.Surface, int]]:
        """当前应绘制的背景层 [(surface, alpha0~255)]，供渲染器合成。"""
        layers: List[Tuple[pygame.Surface, int]] = []
        if self._bg_prev is not None:
            layers.append((self._bg_prev, 255))
            if self._bg_cur is not None:
                a = int(max(0.0, min(1.0, self._bg_progress)) * 255)
                layers.append((self._bg_cur, a))
        elif self._bg_cur is not None:
            layers.append((self._bg_cur, 255))
        return layers

    def draw(self, target: pygame.Surface,
             render_alpha: float = 1.0) -> None:
        """绘制舞台。

        render_alpha < 1.0 时，立绘位置在上一/当前逻辑帧之间插值
        （固定步长补帧渲染）；默认 1.0 与既有行为一致。
        """
        target.fill(STAGE_CLEAR)
        for surf, a in self.background_layers():
            if a >= 255:
                target.blit(surf, (0, 0))
            else:
                surf.set_alpha(a)
                target.blit(surf, (0, 0))
                surf.set_alpha(255)
        interp = max(0.0, min(1.0, render_alpha))
        for spr in self.sorted_sprites():
            if interp >= 1.0:
                spr.draw(target)
            else:
                rx, ry = spr.render_pos(interp)
                spr.draw_at(target, rx, ry)
