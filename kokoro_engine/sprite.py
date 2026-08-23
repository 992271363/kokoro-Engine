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
        self.base_surface = self.surface.copy()   # 距离缩放的采样基准
        self.scale = 1.0                          # 相对 base_surface 的倍率
        self.x = float(x)
        self.y = float(y)
        # 上一逻辑帧位置（固定步长补间渲染插值用）
        self.prev_x = self.x
        self.prev_y = self.y
        # 显示层缩放缓存（renderer 用）：((surface尺寸, 显示尺寸), 缩放面)
        self._disp_cache = None
        self.z = float(z)
        self.alpha = 255.0          # 0~255，淡入从 0 拉起
        self.visible = True
        self.seq = seq              # 同 z 时按加入先后稳定排序
        self.name = sid             # 面板展示用别名，可改

    # ------------------------------------------------------------- 距离缩放
    def set_scale(self, k: float) -> None:
        """以 base_surface 为基准等比缩放（不改变 x/y 锚点语义）。"""
        k = max(0.05, min(4.0, float(k)))
        if abs(k - self.scale) < 1e-6:
            return
        w = max(1, int(self.base_surface.get_width() * k + 0.5))
        h = max(1, int(self.base_surface.get_height() * k + 0.5))
        if (w, h) == self.base_surface.get_size():
            self.surface = self.base_surface.copy()
        else:
            try:
                self.surface = pygame.transform.smoothscale(
                    self.base_surface, (w, h))
            except (pygame.error, ValueError):
                return
        self.scale = k

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

    # ------------------------------------------------------------- 渲染辅助
    def snap_render(self) -> None:
        """手动改写 x/y 后调用：令插值基准与当前一致（无拖影）。"""
        self.prev_x = self.x
        self.prev_y = self.y

    def render_pos(self, alpha: float) -> tuple:
        """上一逻辑帧与当前帧之间按 alpha 线性插值的位置。"""
        rx = self.prev_x + (self.x - self.prev_x) * alpha
        ry = self.prev_y + (self.y - self.prev_y) * alpha
        return rx, ry

    # ------------------------------------------------------------------ 绘制
    def draw(self, target: pygame.Surface) -> None:
        """绘制在逻辑坐标处（alpha=1.0 等价）。"""
        self.draw_at(target, self.x, self.y)

    def draw_at(self, target: pygame.Surface, x: float, y: float) -> None:
        """在指定锚点（底边中心）绘制；供插值渲染使用。"""
        if not self.visible or self.alpha <= 0:
            return
        a = max(0, min(255, int(self.alpha)))
        self.surface.set_alpha(a)
        target.blit(self.surface,
                    (int(x - self.width / 2), int(y - self.height)))

    def __repr__(self) -> str:  # pragma: no cover
        return (f"<Sprite {self.id!r} pos=({self.x:.0f},{self.y:.0f}) "
                f"alpha={self.alpha:.0f} z={self.z}>")
