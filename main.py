"""kokoro-Engine 演示入口。

运行：python main.py
布局：左侧 = 舞台实时渲染区（可点击拾取立绘），右侧 = 控制面板。
"""

from __future__ import annotations

import sys

import pygame

from gui.panel import ControlPanel
from gui.widgets import get_font
from kokoro_engine import Engine

WINDOW_SIZE = (1656, 728)
STAGE_RECT = pygame.Rect(24, 56, 1152, 648)
PANEL_RECT = pygame.Rect(1200, 8, 432, 712)

BG_COLOR = (16, 17, 20)


def stage_pos_to_world(px: int, py: int):
    return px - STAGE_RECT.x, py - STAGE_RECT.y


def main() -> int:
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("kokoro-Engine v0.1 · galgame 演出系统")
    clock = pygame.time.Clock()

    engine = Engine(asset_dir="assets")
    stage_surface = pygame.Surface(engine.size)
    panel = ControlPanel(engine, PANEL_RECT)

    # 开场演出：即时背景 + 左侧立绘淡入，保证首屏不空白
    engine.set_background("bg_school", fade=0.0)
    engine.show_sprite("akari", image="char_akari", pos="left", fade=1.2)
    panel.select_sprite("akari")

    running = True
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    panel._on_toggle_global()
                continue
            if event.type in (pygame.MOUSEBUTTONDOWN,
                              pygame.MOUSEBUTTONUP,
                              pygame.MOUSEMOTION):
                if panel.rect.collidepoint(event.pos):
                    panel.handle_event(event)
                elif event.type == pygame.MOUSEBUTTONDOWN \
                        and event.button == 1 \
                        and STAGE_RECT.collidepoint(event.pos):
                    _pick_sprite(panel, engine, *event.pos)

        engine.update(dt)
        panel.update(dt)

        # ------------------------------------------------------------ 渲染
        screen.fill(BG_COLOR)
        title = get_font(18).render("kokoro-Engine v0.1 — galgame 演出系统",
                                    True, (235, 237, 244))
        screen.blit(title, (STAGE_RECT.x, 20))

        engine.draw(stage_surface)
        screen.blit(stage_surface, STAGE_RECT.topleft)
        pygame.draw.rect(screen, (70, 76, 92), STAGE_RECT, 1)

        st = engine.get_state()
        hint = (f"背景: {st['bg'] or '无'}   立绘: {len(st['sprites'])}   "
                f"活动补间: {engine.tweens.active_count}   "
                f"FPS: {clock.get_fps():.0f}   "
                f"（空格=全局暂停  Esc=退出）")
        bar = get_font(13).render(hint, True, (150, 156, 168))
        screen.blit(bar, (STAGE_RECT.x, STAGE_RECT.bottom + 8))

        panel.draw(screen)
        pygame.display.flip()

    pygame.quit()
    return 0


def _pick_sprite(panel: ControlPanel, engine: Engine,
                 px: int, py: int) -> None:
    sx, sy = stage_pos_to_world(px, py)
    for spr in reversed(engine.stage.sorted_sprites()):   # 前→后拾取
        if spr.contains_point(sx, sy):
            panel.select_sprite(spr.id)
            return
    panel.select_sprite(None)


if __name__ == "__main__":
    sys.exit(main())
