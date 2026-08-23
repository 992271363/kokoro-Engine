"""显示层合成器：直接按窗口分辨率合成舞台画面（带缩放缓存）。

替代"整幅画布每帧 smoothscale"的旧管线：
- 背景缩放结果按 (表面id, 显示尺寸) 缓存（交叉淡入淡出两层各自缓存）；
- 立绘缩放面缓存在 Sprite._disp_cache 上，随实例生命周期自动失效；
- 立绘位置按显示比例换算，锚点语义（水平中心/脚线）不变，
  并支持逻辑帧间插值（alpha 因子由 Engine.advance 提供）。
"""

from __future__ import annotations

from typing import Tuple

import pygame

from .stage import STAGE_CLEAR


class StageRenderer:
    """绑定一个 Engine 的舞台渲染视图。draw() 可每帧安全调用。"""

    MAX_BG_ENTRIES = 8     # 防止极端换图场景下缓存无限增长

    def __init__(self, engine) -> None:
        self.engine = engine
        self._bg_cache = {}   # id(surface) -> (disp_size, scaled_surface)

    # ------------------------------------------------------------------ 缓存
    def _scaled_bg(self, surf: pygame.Surface,
                   disp_size: Tuple[int, int]) -> pygame.Surface:
        key = id(surf)
        entry = self._bg_cache.get(key)
        if entry is not None and entry[0] == disp_size:
            return entry[1]
        scaled = pygame.transform.smoothscale(surf, disp_size)
        if len(self._bg_cache) >= self.MAX_BG_ENTRIES:
            self._bg_cache.clear()
        self._bg_cache[key] = (disp_size, scaled)
        return scaled

    @staticmethod
    def _scaled_sprite(spr, disp_size: Tuple[int, int],
                       sx: float, sy: float) -> pygame.Surface:
        key = (spr.surface.get_size(), disp_size)
        if spr._disp_cache is not None and spr._disp_cache[0] == key:
            return spr._disp_cache[1]
        w = max(1, int(spr.width * sx + 0.5))
        h = max(1, int(spr.height * sy + 0.5))
        if (w, h) == spr.surface.get_size():
            scaled = spr.surface
        else:
            scaled = pygame.transform.smoothscale(spr.surface, (w, h))
        spr._disp_cache = (key, scaled)
        return scaled

    # ------------------------------------------------------------------ 绘制
    def draw(self, target: pygame.Surface, disp_rect: pygame.Rect,
             alpha: float = 1.0) -> None:
        """把舞台合成到 target 的 disp_rect 区域（通常为整屏客户区）。

        alpha 为逻辑帧插值因子（Engine.advance 返回值），1.0 表示
        完全使用当前逻辑帧位置。
        """
        st = self.engine.stage
        sx = disp_rect.w / max(1, st.w)
        sy = disp_rect.h / max(1, st.h)

        target.fill(STAGE_CLEAR, disp_rect)
        for bg_surf, bg_alpha in st.background_layers():
            scaled = self._scaled_bg(bg_surf, disp_rect.size)
            if bg_alpha >= 255:
                target.blit(scaled, disp_rect.topleft)
            else:
                scaled.set_alpha(bg_alpha)
                target.blit(scaled, disp_rect.topleft)
                scaled.set_alpha(255)

        interp = max(0.0, min(1.0, alpha))
        for spr in st.sorted_sprites():
            if not spr.visible or spr.alpha <= 0:
                continue
            rx, ry = spr.render_pos(interp) if interp < 1.0 \
                else (spr.x, spr.y)
            scaled = self._scaled_sprite(spr, disp_rect.size, sx, sy)
            sw, sh = scaled.get_size()
            dx = rx * sx
            dy = ry * sy
            a = max(0, min(255, int(spr.alpha)))
            scaled.set_alpha(a)
            target.blit(scaled,
                        (int(dx - sw / 2), int(dy - sh)))
