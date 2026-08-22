"""立绘对象：持有图像与显示状态（位置 / 透明度 / 层级 / 可见性）。

坐标语义：x 为立绘水平中心，y 为立绘底边（脚线）。
z 值越大越靠前；z 相同时按添加顺序稳定排序。
"""

from __future__ import annotations

from typing import Optional

import pygame


class Sprite:
    def __init__(self, sid: str, surface: pygame.Surface,
                 x: float, y: float, z: float = 0.0,
                 seq: int = 0) -> None:
        self.id = sid
        try:
            self.surface = surface.convert_alpha()
        except pygame.error:
            self.surface = surface.copy()
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.alpha = 255.0          # 0~255，淡入从 0 拉起
        self.visible = True
        self.seq = seq              # 同 z 时按加入先后稳定排序
        self.name = sid             # 面板展示用别名，可改

    # ------------------------------------------------------------------ 几何
    @property
    def width(self) -> int:
        return self.surface.get_width()

    @property
    def height(self) -> int:
        return self.surface.get_height()

    def get_rect(self) -> pygame.Rect:
        """以 (底边中心 x, 底边 y) 锚点计算的目标矩形。"""
        return pygame.Rect(int(self.x - self.width / 2),
                           int(self.y - self.height),
                           self.width, self.height)

    def contains_point(self, px: float, py: float) -> bool:
        return self.visible and self.alpha > 10 and \
            self.get_rect().collidepoint(px, py)

    # ------------------------------------------------------------------ 更新
    def draw(self, target: pygame.Surface) -> None:
        if not self.visible or self.alpha <= 0:
            return
        a = max(0, min(255, int(self.alpha)))
        self.surface.set_alpha(a)
        target.blit(self.surface, self.get_rect())

    def __repr__(self) -> str:  # pragma: no cover
        return (f"<Sprite {self.id!r} pos=({self.x:.0f},{self.y:.0f}) "
                f"alpha={self.alpha:.0f} z={self.z}>")
