"""资源库：图片加载、缓存、目录浏览与占位图生成。

约定：
- assets/ 目录（含任意子目录）中的图片都会被扫描。
- 资源键 = 相对 assets/ 的路径（不含扩展名，统一用 / 分隔），
  如根目录的 "bg_school"、子目录里的 "school/bg1"。
- 分类由目录结构表达，不依赖文件名前缀；同名文件在不同子目录互不冲突。
- 若请求的键不存在对应文件，则按调用方显式给出的 kind（"bg"/"char"/None）
  程序化生成一张确定性占位图，保证无素材也能完整体验演出功能。
"""

from __future__ import annotations

import hashlib
import os
from typing import Dict, List, Optional, Tuple

import pygame

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

# 目录分类约定：assets/bg/** = 背景，assets/fg/** = 立绘（前景）。
# GUI 列表与浏览器按此分类；分类之外的文件不进 GUI（API 仍可加载）。
BG_ROOT = "bg"
FG_ROOT = "fg"

# 分类子树完全为空时提供的占位伪条目（运行时生成，不落盘）
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
        self._thumb_cache: Dict[str, pygame.Surface] = {}
        self._file_index: Dict[str, str] = {}
        self._scan_dir()

    # ------------------------------------------------------------------ 扫描
    def _scan_dir(self) -> None:
        """递归扫描；键为相对 asset_dir 的路径（无扩展名，/ 分隔）。"""
        self._file_index.clear()
        if not os.path.isdir(self.asset_dir):
            return
        for root, dirs, files in os.walk(self.asset_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fn in files:
                if fn.lower().endswith(IMAGE_EXTS):
                    path = os.path.join(root, fn)
                    rel = os.path.relpath(path, self.asset_dir)
                    key = os.path.splitext(rel)[0].replace(os.sep, "/")
                    self._file_index[key] = path

    def rescan(self) -> None:
        self._cache.clear()          # 文件可能已增删，全尺寸缓存一并失效
        self._scan_dir()

    # ------------------------------------------------------------------ 浏览
    def all_images(self, kind: Optional[str] = None) -> List[str]:
        """资源键列表（排序）。

        kind="bg" → 仅 assets/bg/ 子树；"fg" → 仅 assets/fg/ 子树；
        None → 全部。对应分类子树为空时回退到该类的占位伪条目。
        """
        found = sorted(self._file_index.keys())
        if kind == "bg":
            sub = [k for k in found if k.startswith(BG_ROOT + "/")]
            return sub if sub else list(FALLBACK_BACKGROUNDS)
        if kind == "fg":
            sub = [k for k in found if k.startswith(FG_ROOT + "/")]
            return sub if sub else list(FALLBACK_CHARACTERS)
        return found

    def list_dir(self, rel: str = "") -> Tuple[List[str], List[str]]:
        """浏览器导航：返回 (rel 下子目录名列表, 直属图片键列表)，均已排序。"""
        rel = (rel or "").strip("/").strip()
        prefix = f"{rel}/" if rel else ""
        dirs_set, images = set(), []
        for key in self._file_index:
            if not key.startswith(prefix):
                continue
            rest = key[len(prefix):]
            if "/" in rest:
                dirs_set.add(rest.split("/", 1)[0])
            else:
                images.append(key)
        # 空目录兜底：在分类根且无文件时给出占位伪条目
        if rel in (BG_ROOT, FG_ROOT) and not dirs_set and not images:
            images = (list(FALLBACK_BACKGROUNDS) if rel == BG_ROOT
                      else list(FALLBACK_CHARACTERS))
        return sorted(dirs_set), sorted(images)

    def has_file(self, name: str) -> bool:
        return name in self._file_index

    # ------------------------------------------------------------------ 获取
    def get(self, name: str, size: Optional[Tuple[int, int]] = None,
            alpha: bool = True, kind: Optional[str] = None) -> pygame.Surface:
        """按键取图。文件存在则加载（可缩放到 size），否则按 kind 生成占位图。

        kind: "bg"=背景渐变风, "char"=人形剪影, None=通用色块。
        """
        cache_key = f"{name}|{size}|{alpha}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if name in self._file_index:
            try:
                surf = pygame.image.load(self._file_index[name])
                surf = _safe_convert(surf, alpha)
                if size is not None and surf.get_size() != tuple(size):
                    surf = pygame.transform.smoothscale(surf, size)
            except (pygame.error, ValueError) as exc:  # 损坏/不支持的格式
                print(f"[assets] 加载 {name} 失败({exc})，使用占位图。")
                surf = self.make_placeholder(name, size or (800, 600),
                                             alpha, kind=kind)
        else:
            surf = self.make_placeholder(name, size or (800, 600),
                                         alpha, kind=kind)

        self._cache[cache_key] = surf
        return surf

    def get_thumbnail(self, name: str,
                      box: Tuple[int, int] = (52, 52)) -> pygame.Surface:
        """等比缩放到 box 内的缩略图（惰性生成并缓存）。"""
        cache_key = f"{name}|{box}"
        if cache_key in self._thumb_cache:
            return self._thumb_cache[cache_key]
        src = self.get(name, alpha=True)
        w, h = src.get_size()
        scale = min(box[0] / max(1, w), box[1] / max(1, h))
        tw, th = max(1, int(w * scale)), max(1, int(h * scale))
        try:
            thumb = pygame.transform.smoothscale(src, (tw, th))
        except (pygame.error, ValueError):
            thumb = src
        self._thumb_cache[cache_key] = thumb
        return thumb

    # -------------------------------------------------------------- 占位生成
    def make_placeholder(self, name: str, size: Tuple[int, int],
                         alpha: bool = True,
                         kind: Optional[str] = None) -> pygame.Surface:
        """按显式 kind 生成占位图："bg"=背景渐变风，"char"=人形剪影，
        None=通用色块。不依赖文件名前缀。"""
        w, h = size
        if kind == "bg":
            surf = self._placeholder_background(name, w, h)
        elif kind == "char":
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
