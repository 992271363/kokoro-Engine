"""把运行时占位图导出为真实 PNG 文件到 assets/ 目录。

生成的文件与引擎内置占位图像素级一致（同名同图），之后可直接用
自己的素材替换同名文件。想重新生成时再跑一次本脚本即可。

用法：
    python tools/export_placeholders.py
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from kokoro_engine import Engine  # noqa: E402
from kokoro_engine.assets import (FALLBACK_BACKGROUNDS,  # noqa: E402
                                  FALLBACK_CHARACTERS, AssetLibrary)


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    asset_dir = os.path.join(root, "assets")
    bg_dir = os.path.join(asset_dir, "bg")
    fg_dir = os.path.join(asset_dir, "fg")
    os.makedirs(bg_dir, exist_ok=True)
    os.makedirs(fg_dir, exist_ok=True)

    if not pygame.get_init():
        pygame.init()
    stage_w, stage_h = Engine.DEFAULT_STAGE_SIZE

    char_h = int(stage_h * Engine.CHAR_MAX_H_FRAC)
    char_w = int(char_h * Engine.CHAR_PLACEHOLDER_ASPECT)

    lib = AssetLibrary(asset_dir)
    # 输出：<分类根>/<干净名>.png，对应键 bg/school、fg/akari 等
    exports = [(bg_dir, name.replace("bg_", ""), (stage_w, stage_h), "bg")
               for name in FALLBACK_BACKGROUNDS] + \
              [(fg_dir, name.replace("char_", ""), (char_w, char_h), "char")
               for name in FALLBACK_CHARACTERS]

    for out_dir, clean, size, kind in exports:
        surf = lib.make_placeholder(clean, size, alpha=True, kind=kind)
        out_path = os.path.join(out_dir, f"{clean}.png")
        pygame.image.save(surf, out_path)
        print(f"生成 {os.path.relpath(out_path, root)}  {size[0]}x{size[1]}")

    print(f"完成，共 {len(exports)} 张。替换同名文件即可使用自定义素材。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
