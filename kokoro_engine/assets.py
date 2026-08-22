"""资源库：图片加载、缓存与占位图生成。

约定：
- assets/ 目录下任意子目录中的图片文件都会被扫描。
- 文件名以 bg_ 开头视为背景，以 char_ 开头视为立绘；其余按扩展名归类失败时忽略。
- 若请求的名字不存在对应文件，则程序化生成一张确定性占位图（同名同图），
  保证无素材也能完整体验演出功能。
"""

from __future__ import annotations

import hashlib
import os
from typing import Dict, List, Optional, Tuple

import pygame

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

# 占位背景名 / 立绘图名（无素材时提供开箱即用的选择）
FALLBACK_BACKGROUNDS = ["bg_school", "bg_room", "bg_street", "bg_night"]
FALLBACK_CHARACTERS = ["char_akari", "char_hinata", "char_kaoru", "char_sora"]


def _hash_color(name: str, salt: int = 0) -> Tuple[int, int, int]:
    h = hashlib.md5(f"{name}#{salt}".encode("utf-8")).digest()
    return h[0], h[1], h[2]


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _safe_convert(surf: pygame.Surface, alpha: bool) -> pygame.Surface:
    """convert* 需要已设置显示模式；无窗口环境（测试/工具脚本）直接返回原图。"""
    try:
        return surf.convert_alpha() if alpha else surf.convert()
    except pygame.error:
        return surf


class AssetLibrary:
    """负责所有图像资源的查找、加载、缓存与占位生成。"""

    def __init__(self, asset_dir: str = "assets") -> None:
        self.asset_dir = asset_dir
        self._cache: Dict[str, pygame.Surface] = {}
        self._file_index: Dict[str, str] = {}
        self._scan_dir()

    # ------------------------------------------------------------------ 扫描
    def _scan_dir(self) -> None:
        self._file_index.clear()
        if not os.path.isdir(self.asset_dir):
            return
        for root, _dirs, files in os.walk(self.asset_dir):
            for fn in files:
                if fn.lower().endswith(IMAGE_EXTS):
                    key = os.path.splitext(fn)[0]
                    path = os.path.join(root, fn)
                    self._file_index[key] = path

    def rescan(self) -> None:
        self._scan_dir()

    # ------------------------------------------------------------------ 列表
    def backgrounds(self) -> List[str]:
        found = sorted(k for k in self._file_index if k.startswith("bg_"))
        return found if found else list(FALLBACK_BACKGROUNDS)

    def characters(self) -> List[str]:
        found = sorted(k for k in self._file_index if k.startswith("char_"))
        return found if found else list(FALLBACK_CHARACTERS)

    def has_file(self, name: str) -> bool:
        return name in self._file_index

    # ------------------------------------------------------------------ 获取
    def get(self, name: str, size: Optional[Tuple[int, int]] = None,
            alpha: bool = True) -> pygame.Surface:
        """按名字取图。文件存在则加载（可缩放到 size），否则生成占位图。"""
        cache_key = f"{name}|{size}|{alpha}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if name in self._file_index:
            try:
                surf = pygame.image.load(self._file_index[name])
                surf = _safe_convert(surf, alpha)
                if size is not None and surf.get_size() != tuple(size):
                    surf = pygame.transform.smoothscale(surf, size)
            except pygame.error as exc:  # 文件损坏等情况回退到占位图
                print(f"[assets] 加载 {name} 失败({exc})，使用占位图。")
                surf = self.make_placeholder(name, size or (800, 600), alpha)
        else:
            surf = self.make_placeholder(name, size or (800, 600), alpha)

        self._cache[cache_key] = surf
        return surf

    # -------------------------------------------------------------- 占位生成
    def make_placeholder(self, name: str, size: Tuple[int, int],
                         alpha: bool = True) -> pygame.Surface:
        w, h = size
        if name.startswith("bg_"):
            surf = self._placeholder_background(name, w, h)
        elif name.startswith("char_"):
            surf = self._placeholder_character(name, w, h)
        else:
            surf = self._placeholder_generic(name, w, h)
        return _safe_convert(surf, alpha)

    @staticmethod
    def _placeholder_background(name: str, w: int, h: int) -> pygame.Surface:
        c1 = _hash_color(name, salt=1)
        c2 = _hash_color(name, salt=2)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        # 垂直渐变天空
        for y in range(h):
            t = y / max(1, h - 1)
            col = (
                int(_lerp(c1[0], c2[0], t)),
                int(_lerp(c1[1], c2[1], t)),
                int(_lerp(c1[2], c2[2], t)),
            )
            pygame.draw.line(surf, col, (0, y), (w, y))
        rng = hashlib.md5(name.encode()).digest()
        # 远山剪影
        hill_col = (max(0, c1[0] // 3), max(0, c1[1] // 3), max(0, c1[2] // 3))
        pts = [(0, h)]
        for i in range(9):
            x = w * i / 8
            peak = h * (0.62 + (rng[i] / 255) * 0.18)
            pts.append((x, peak))
        pts.append((w, h))
        pygame.draw.polygon(surf, hill_col, pts)
        # 地面
        ground = (max(0, c2[0] // 4), max(0, c2[1] // 4), max(0, c2[2] // 4))
        pygame.draw.rect(surf, ground, (0, int(h * 0.82), w, int(h * 0.18)))
        # 名字水印
        font = _water_font(int(h * 0.06))
        label = font.render(name, True, (255, 255, 255))
        shadow = font.render(name, True, (0, 0, 0))
        pos = (w // 2 - label.get_width() // 2, int(h * 0.08))
        surf.blit(shadow, (pos[0] + 2, pos[1] + 2))
        surf.blit(label, pos)
        return surf

    @staticmethod
    def _placeholder_character(name: str, w: int, h: int) -> pygame.Surface:
        base = _hash_color(name, salt=3)
        dark = tuple(max(0, v // 2) for v in base)
        skin = (245, 220, 195)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx = w // 2
        # 比例：全身人形剪影
        head_r = int(w * 0.16)
        head_cy = int(h * 0.13)
        body_top = head_cy + head_r
        body_w = int(w * 0.42)
        body_h = int(h * 0.52)
        leg_h = h - (body_top + body_h)
        # 头发（比头大一圈的圆）
        pygame.draw.circle(surf, dark, (cx, head_cy), int(head_r * 1.18))
        # 脸
        pygame.draw.circle(surf, skin, (cx, head_cy + int(head_r * 0.15)), head_r)
        # 眼睛
        eye_y = head_cy + int(head_r * 0.35)
        eye_dx = int(head_r * 0.42)
        for dx in (-eye_dx, eye_dx):
            pygame.draw.ellipse(surf, (40, 45, 60),
                                (cx + dx - head_r // 5, eye_y,
                                 head_r // 2.5, head_r // 2))
        # 身体（圆角矩形近似）
        pygame.draw.rect(surf, base,
                         (cx - body_w // 2, body_top, body_w, body_h),
                         border_radius=int(body_w // 3))
        # 手臂
        arm_w = int(body_w * 0.28)
        pygame.draw.rect(surf, base,
                         (cx - body_w // 2 - arm_w // 2, body_top + int(body_h * 0.08),
                          arm_w, int(body_h * 0.72)), border_radius=arm_w // 2)
        pygame.draw.rect(surf, base,
                         (cx + body_w // 2 - arm_w // 2, body_top + int(body_h * 0.08),
                          arm_w, int(body_h * 0.72)), border_radius=arm_w // 2)
        # 腿
        leg_w = int(body_w * 0.36)
        gap = int(body_w * 0.12)
        for dx in (-(gap + leg_w // 2), gap + leg_w // 2):
            pygame.draw.rect(surf, dark,
                             (cx + dx - leg_w // 2, body_top + body_h - 4,
                              leg_w, leg_h + 4), border_radius=leg_w // 3)
        # 名字牌
        font = _water_font(max(14, int(h * 0.035)))
        label = font.render(name.replace("char_", ""), True, (255, 255, 255))
        tag_w = label.get_width() + 16
        tag_rect = pygame.Rect(cx - tag_w // 2, h - label.get_height() - 10,
                               tag_w, label.get_height() + 8)
        pygame.draw.rect(surf, (20, 20, 26), tag_rect, border_radius=6)
        surf.blit(label, (tag_rect.x + 8, tag_rect.y + 4))
        return surf

    @staticmethod
    def _placeholder_generic(name: str, w: int, h: int) -> pygame.Surface:
        col = _hash_color(name)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((*col, 255))
        font = _water_font(int(h * 0.1))
        label = font.render(name, True, (255, 255, 255))
        surf.blit(label, (w // 2 - label.get_width() // 2,
                          h // 2 - label.get_height() // 2))
        return surf


_font_cache: dict = {}


def _water_font(size: int) -> pygame.font.Font:
    """占位图内部使用的字体：优先微软雅黑，失败用默认字体。"""
    if not pygame.font.get_init():
        pygame.font.init()
    key = ("water", size)
    if key not in _font_cache:
        try:
            _font_cache[key] = pygame.font.Font(
                r"C:\Windows\Fonts\msyh.ttc", size)
        except Exception:
            _font_cache[key] = pygame.font.Font(None, size)
    return _font_cache[key]
