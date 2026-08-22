"""kokoro_engine：轻量 galgame 演出引擎（Python + pygame-ce）。

对外入口：
    from kokoro_engine import Engine
"""

from .engine import Engine
from .sprite import Sprite
from .stage import Stage, PRESET_X_FRAC
from .tween import EASINGS, Tween, TweenManager
from .timeline import TimelinePlayer

__all__ = [
    "Engine", "Sprite", "Stage", "PRESET_X_FRAC",
    "EASINGS", "Tween", "TweenManager", "TimelinePlayer",
]
__version__ = "0.1.0"
