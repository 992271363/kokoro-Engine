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
        self._bg_version_seen = -1
        self._bg_cache = {}   # (层槽位0=prev/1=cur, disp_size) -> scaled

    # ------------------------------------------------------------------ 缓存
    def _bg_cache_dict(self, disp_size: Tuple[int, int]):
        """按背景版本取缓存字典；版本变化即整体作废。

        键不含 surface id——规避 CPython id() 复用导致的陈旧缓存
        （表现为渲染残留/画布偏移）。
        """
        st = self.engine.stage
        if st.bg_version != self._bg_version_seen:
            self._bg_version_seen = st.bg_version
            self._bg_cache.clear()
        return self._bg_cache

    def _scaled_bg(self, slot: int, surf: pygame.Surface,
                   disp_size: Tuple[int, int]) -> pygame.Surface:
        if surf.get_size() == tuple(disp_size):
            return surf                       # 同尺寸直通，保证逐像素一致
        cache = self._bg_cache_dict(disp_size)
        key = (slot, disp_size)
        entry = cache.get(key)
        if entry is not None:
            return entry
        scaled = pygame.transform.smoothscale(surf, disp_size)
        if len(cache) >= self.MAX_BG_ENTRIES:
            cache.clear()
        cache[key] = scaled
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
        for slot, (bg_surf, bg_alpha) in enumerate(
                st.background_layers()):
            scaled = self._scaled_bg(slot, bg_surf, disp_rect.size)
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
