"""补间动画：缓动函数、单个补间与补间管理器。

Tween 绑定 (对象, 属性名)，在 duration 秒内把属性从当前值插值到目标值。
每帧由 TweenManager.update(dt) 驱动。移动类语义（X轴/Y轴/XY轴）
由调用方决定为哪个属性创建补间——单轴移动不应触碰另一轴。
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Union

Number = Union[int, float]

# ------------------------------------------------------------------ 缓动函数
EASINGS: Dict[str, Callable[[float], float]] = {
    "linear": lambda t: t,
    "ease_in": lambda t: t * t,
    "ease_out": lambda t: 1 - (1 - t) * (1 - t),
    "ease_in_out": lambda t: 3 * t * t - 2 * t * t * t,
    "sine_in_out": lambda t: -(math.cos(math.pi * t) - 1) / 2,
}


def easing_by_name(name: str) -> Callable[[float], float]:
    return EASINGS.get(name, EASINGS["linear"])


class Tween:
    """对 obj.attr 做时长插值。"""

    __slots__ = ("obj", "attr", "from_val", "to_val", "duration",
                 "elapsed", "easing", "on_complete", "_done")

    def __init__(self, obj: object, attr: str, from_val: Number, to_val: Number,
                 duration: float, easing: str = "linear",
                 on_complete: Optional[Callable[[], None]] = None) -> None:
        self.obj = obj
        self.attr = attr
        self.from_val = float(from_val)
        self.to_val = float(to_val)
        self.duration = max(0.0, float(duration))
        self.elapsed = 0.0
        self.easing = easing
        self.on_complete = on_complete
        self._done = self.duration <= 0.0

    @property
    def done(self) -> bool:
        return self._done

    def update(self, dt: float) -> None:
        if self._done:
            return
        self.elapsed += dt
        t = 1.0 if self.duration <= 0 else min(1.0, self.elapsed / self.duration)
        eased = easing_by_name(self.easing)(t)
        setattr(self.obj, self.attr, self.from_val + (self.to_val - self.from_val) * eased)
        if t >= 1.0:
            self._done = True
            if self.on_complete is not None:
                cb, self.on_complete = self.on_complete, None
                cb()

    def cancel(self) -> None:
        self._done = True


class TweenManager:
    """集中管理活动补间；同一 (对象, 属性) 的新补间会取消旧补间。"""

    def __init__(self) -> None:
        self._tweens: List[Tween] = []

    def add(self, tween: Tween) -> Tween:
        self.kill(tween.obj, tween.attr)
        # 立即清掉被取消的，避免列表膨胀
        self._tweens = [tw for tw in self._tweens if not tw.done]
        self._tweens.append(tween)
        return tween

    def tween_attr(self, obj: object, attr: str, to_value: Number,
                   duration: float, easing: str = "linear",
                   on_complete: Optional[Callable[[], None]] = None) -> Tween:
        return self.add(Tween(obj, attr, getattr(obj, attr), to_value,
                              duration, easing, on_complete))

    def kill(self, obj: object, attr: Optional[str] = None) -> None:
        for tw in self._tweens:
            if tw.obj is obj and (attr is None or tw.attr == attr):
                tw.cancel()

    def has_tween(self, obj: object, attr: Optional[str] = None) -> bool:
        return any(not tw.done and tw.obj is obj
                   and (attr is None or tw.attr == attr)
                   for tw in self._tweens)

    def all_tweens(self) -> List[Tween]:
        """当前活动补间快照（供引擎在画布缩放时同步坐标目标）。"""
        return list(self._tweens)

    def update(self, dt: float) -> None:
        for tw in self._tweens:
            tw.update(dt)
        self._tweens = [tw for tw in self._tweens if not tw.done]

    def clear(self) -> None:
        for tw in self._tweens:
            tw.cancel()
        self._tweens.clear()

    @property
    def active_count(self) -> int:
        return len(self._tweens)
