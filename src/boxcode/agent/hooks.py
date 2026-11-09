"""工具钩子：不改主循环，就能检查每次工具调用、改写工具结果（审计、输出脱敏这类功能挂在这里）。

做法借鉴 DeepSeek Harness 的 pre / post 管线。但它的插件可以直接放行、甚至替换执行本身，
而这里的权限策略和沙盒是安全边界，钩子只能在外面加限制：
- before 只能收紧：权限策略先判断，钩子的结论只有更严才生效，放行被拒绝的调用、跳过用户确认都做不到
- 没有包住执行的钩子：能包住，就能不走沙盒
- 钩子拿到的参数是拷贝：权限策略是按原参数判断的，钩子改了参数也影响不到真正执行的那一份
- 钩子出错按失败处理：before 出错就拒绝这次调用；after 出错就丢掉输出，脱敏钩子挂了不能把原文交给模型
- after 能改文字，但不能把失败改成成功；主循环在所有钩子之后才截断输出，钩子撑不爆上下文

钩子在 Agent 线程里同步执行，要快：执行期间按“停止”要等它返回。
"""

import traceback
from collections.abc import Sequence
from dataclasses import dataclass, replace

from pydantic import BaseModel

from boxcode.policy import Action, Decision
from boxcode.tools import Risk, Target, ToolResult
from boxcode.trace import TraceRecorder


@dataclass(frozen=True)
class HookCall:
    """钩子看到的这次调用。只给名字不给工具对象：钩子不需要、也不应该能自己执行工具。"""

    tool: str
    risk: Risk
    params: BaseModel
    target: Target
    turn: int

    def copy(self) -> "HookCall":
        return replace(self, params=self.params.model_copy(deep=True))


class ToolHook:
    """子类只覆盖需要的方法。"""

    def before(self, call: HookCall, decision: Decision) -> Decision | None:
        """工具执行前调用，decision 是目前的结论。返回 None 表示没意见，返回的结论比 decision 宽松时被忽略。"""
        return None

    def after(self, call: HookCall, result: ToolResult) -> ToolResult:
        """工具真的开始执行之后才调用（包括执行失败）；被拒绝、参数不对的调用不会走到这里。"""
        return result


class ToolHooks:
    """按顺序跑钩子，并保证它们越不过模块说明里的那些限制。"""

    def __init__(self, hooks: Sequence[ToolHook], trace: TraceRecorder) -> None:
        self._hooks = tuple(hooks)
        self._trace = trace

    def before(self, call: HookCall, decision: Decision) -> Decision:
        for hook in self._hooks:
            if decision.action is Action.DENY:  # 已经是最严的结论
                break
            name = type(hook).__name__
            try:
                proposed = hook.before(call.copy(), decision)
                tightened = decision if proposed is None else decision.tightened_by(proposed)
            except Exception as e:
                self._record_error(hook, "before", call, e)
                # 给模型看的只有异常类型：消息里可能带着钩子正在处理的内容，完整信息在轨迹里
                return Decision(Action.DENY, f"钩子 {name} 出错（{type(e).__name__}），按拒绝处理")
            if tightened is not decision:
                decision = Decision(tightened.action, f"钩子 {name}：{tightened.reason}")
        return decision

    def after(self, call: HookCall, result: ToolResult) -> ToolResult:
        for hook in self._hooks:
            try:
                changed = hook.after(call.copy(), result)
                result = ToolResult(changed.text, result.ok and changed.ok)
            except Exception as e:
                self._record_error(hook, "after", call, e)
                return ToolResult(f"错误：钩子 {type(hook).__name__} 处理结果时出错（{type(e).__name__}），输出已丢弃",
                                  ok=False)
        return result

    def _record_error(self, hook: ToolHook, stage: str, call: HookCall, e: Exception) -> None:
        self._trace.emit("hook_error", turn=call.turn, tool=call.tool, hook=type(hook).__name__, stage=stage,
                         error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc())
