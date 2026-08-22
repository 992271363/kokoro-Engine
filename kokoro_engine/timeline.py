"""时间轴/序列系统：把声明式步骤表编译为可播放的演出序列。

步骤格式（每步恰好一个动作键）：
    {"bg": 名字,            "fade": 秒}
    {"show": 立绘id,        "img": 图名, "pos": 预设位|(x,y), "fade": 秒, "z": 层值}
    {"hide": 立绘id,        "fade": 秒}
    {"move": 立绘id,        "to": 预设位|(x,y), "dur": 秒, "easing": 名称}
    {"alpha": 立绘id,       "value": 0~255, "dur": 秒}
    {"layer": 立绘id,       "op": "front"|"back"|"up"|"down"|"set", "z": 值}
    {"wait": 秒}
    {"call": 可调用对象}                       # 自定义即时回调
    {"parallel": [子步骤, ...]}                # 同时开始，段长取最长者

顺序执行；每段时长由动作自身的 fade/dur/wait 决定。
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Union

Step = Dict

# 播放器状态
IDLE = "idle"
PLAYING = "playing"
PAUSED = "paused"
DONE = "done"


class _Segment:
    __slots__ = ("actions", "duration")

    def __init__(self, actions: List[Callable[[], None]], duration: float) -> None:
        self.actions = actions
        self.duration = max(0.0, float(duration))


def _num(step: Step, *keys: str, default: float) -> float:
    for k in keys:
        if k in step and step[k] is not None:
            return float(step[k])
    return default


class TimelinePlayer:
    """驱动一段编译后的时间轴。所有实际演出都通过 Engine 的公开 API 完成。"""

    def __init__(self) -> None:
        self._segments: List[_Segment] = []
        self._index = 0
        self._countdown = 0.0
        self.state = IDLE
        self.engine = None  # 由 Engine 构造时注入

    # ------------------------------------------------------------------ 编译
    def compile(self, steps: List[Step]) -> None:
        """编译（不播放）。格式错误立即抛 ValueError。"""
        compiled: List[_Segment] = []
        for i, step in enumerate(steps):
            try:
                compiled.extend(self._compile_step(step))
            except Exception as exc:
                raise ValueError(f"时间轴第 {i} 步无法编译: {step!r} ({exc})") from exc
        self.stop()
        self._segments = compiled
        self.state = IDLE

    def _compile_step(self, step: Step, engine=None) -> List[_Segment]:
        eng = engine if engine is not None else self.engine
        keys = [k for k in ("bg", "show", "hide", "move", "alpha",
                            "layer", "wait", "call", "parallel") if k in step]
        if len(keys) != 1:
            raise ValueError("每个步骤必须有且只有一个动作键 "
                             "(bg/show/hide/move/alpha/layer/wait/call/parallel)")
        key = keys[0]

        if key == "bg":
            fade = _num(step, "fade", default=0.5)
            return [_Segment([lambda: eng.set_background(step["bg"], fade=fade)], fade)]

        if key == "show":
            sid = step["show"]
            pos = step.get("pos", "center")
            fade = _num(step, "fade", default=0.6)
            z = step.get("z")
            return [_Segment(
                [lambda: eng.show_sprite(sid, image=step.get("img"), pos=pos,
                                         fade=fade, z=z)], fade)]

        if key == "hide":
            sid = step["hide"]
            fade = _num(step, "fade", default=0.6)
            return [_Segment([lambda: eng.hide_sprite(sid, fade=fade)], fade)]

        if key == "move":
            sid = step["move"]
            to = step.get("to", "center")
            dur = _num(step, "dur", default=1.0)
            easing = step.get("easing", "ease_in_out")
            return [_Segment([lambda: eng.move_sprite(sid, to=to, dur=dur,
                                                      easing=easing)], dur)]

        if key == "alpha":
            sid = step["alpha"]
            value = float(step.get("value", 255))
            dur = _num(step, "dur", default=0.5)
            return [_Segment([lambda: eng.fade_to(sid, value=value, dur=dur)], dur)]

        if key == "layer":
            sid = step["layer"]
            op = step.get("op", "front")
            z = step.get("z", 0)

            def do_layer() -> None:
                if op == "front":
                    eng.bring_to_front(sid)
                elif op == "back":
                    eng.send_to_back(sid)
                elif op == "up":
                    eng.layer_up(sid)
                elif op == "down":
                    eng.layer_down(sid)
                elif op == "set":
                    eng.set_z(sid, z)
                else:
                    raise ValueError(f"未知层级操作: {op}")

            return [_Segment([do_layer], 0.0)]

        if key == "wait":
            dur = _num(step, "wait", default=0.5)
            return [_Segment([], dur)]

        if key == "call":
            fn = step["call"]
            if not callable(fn):
                raise TypeError("call 必须是可调用对象")
            return [_Segment([fn], 0.0)]

        # parallel：递归编译子步骤，合并为一段同时触发
        subs = step["parallel"]
        if not isinstance(subs, list):
            raise TypeError("parallel 需要步骤列表")
        merged_actions: List[Callable[[], None]] = []
        max_dur = 0.0
        for sub in subs:
            for seg in self._compile_step(sub):
                merged_actions.extend(seg.actions)
                max_dur = max(max_dur, seg.duration)
        return [_Segment(merged_actions, max_dur)]

    # ------------------------------------------------------------------ 播放
    def play(self, steps: Optional[List[Step]] = None,
             engine=None) -> None:
        if engine is not None:
            self.engine = engine
        if steps is not None:
            self.compile(steps)
        if not self._segments:
            self.state = DONE
            return
        self._index = -1
        self.state = PLAYING
        self._advance()          # 立即触发第一段

    def stop(self) -> None:
        self._segments = []
        self._index = 0
        self._countdown = 0.0
        self.state = IDLE

    @property
    def paused(self) -> bool:
        return self.state == PAUSED

    def pause(self) -> None:
        if self.state == PLAYING:
            self.state = PAUSED

    def resume(self) -> None:
        if self.state == PAUSED:
            self.state = PLAYING

    def toggle_pause(self) -> bool:
        if self.paused:
            self.resume()
        else:
            self.pause()
        return self.paused

    def _advance(self) -> None:
        """弹出下一段并立即执行其动作。"""
        self._index += 1
        while self._index < len(self._segments):
            seg = self._segments[self._index]
            for act in seg.actions:
                act()
            if seg.duration > 0:
                self._countdown = seg.duration
                return
            self._index += 1     # 零时长段直接串联
        self.state = DONE

    def update(self, dt: float) -> None:
        if self.state != PLAYING:
            return
        self._countdown -= dt
        if self._countdown <= 0:
            self._advance()

    # ------------------------------------------------------------------ 状态
    @property
    def progress_text(self) -> str:
        total = len(self._segments)
        cur = min(total, max(0, self._index + 1))
        return f"{cur}/{total}" if total else "-"

    @property
    def busy(self) -> bool:
        return self.state in (PLAYING, PAUSED)
