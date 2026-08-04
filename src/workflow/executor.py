"""步骤执行器 StepExecutor

根据步骤 type 分发执行：
- action: 实例化 Action → 解析 config 变量 → on_error 策略 → 写入 step_output
- condition: evaluate_condition → 返回 {goto: if_true/if_false}
- switch: 匹配 cases → 返回 {goto: ...}
- loop: 遍历 items 执行子步骤

on_error 策略（在 _execute_with_retry 中统一处理）：
- continue / skip: 记录警告，继续
- abort: 抛异常，中止整个流程
- retry_then_skip: 指数退避重试 3 次，仍失败则跳过
- retry_then_abort: 重试 3 次，仍失败则中止
"""

from __future__ import annotations

import re
import time
from typing import Any

from src.core.logger import get_logger
from src.workflow.actions.auto_reply import AutoReplyAction
from src.workflow.actions.base import BaseAction
from src.workflow.actions.check_duplicate import CheckDuplicateAction
from src.workflow.actions.execute_script import ExecuteScriptAction
from src.workflow.actions.extract_info import ExtractInfoAction
from src.workflow.actions.forward import ForwardAction
from src.workflow.actions.http_request import HttpRequestAction
from src.workflow.actions.log import LogAction
from src.workflow.actions.move_to_folder import MoveToFolderAction
from src.workflow.actions.notify import NotifyAction
from src.workflow.actions.save_attachment import SaveAttachmentAction
from src.workflow.actions.save_record import SaveRecordAction
from src.workflow.actions.set_variable import SetVariableAction
from src.workflow.actions.summarize import SummarizeAction
from src.workflow.actions.tag import TagAction
from src.workflow.condition import evaluate_condition
from src.workflow.context import WorkflowContext

logger = get_logger("workflow.executor")

# 重试退避间隔（秒）：1, 3, 9
_RETRY_DELAYS = [1, 3, 9]
_DEFAULT_MAX_RETRIES = 3

# 整串变量引用匹配：${xxx}
_FULL_VAR_PATTERN = re.compile(r"^\$\{[^}]+\}$")
# 任意变量引用
_VAR_PATTERN = re.compile(r"\$\{[^}]+\}")


class StepExecutor:
    """步骤执行器：负责单个步骤的解析、执行与错误处理。"""

    def __init__(self, action_dependencies: dict):
        """初始化执行器。

        Args:
            action_dependencies: 引擎注入的依赖字典，键为：
                notification_engine / llm_client / smtp_client /
                mail_repository / imap_client / execution_repo / secret_mgr
        """
        self.deps = action_dependencies or {}
        self._action_classes = self._register_actions()

    @staticmethod
    def _register_actions() -> dict[str, type[BaseAction]]:
        """注册内置 Action 名称 → 类映射。"""
        return {
            "notify": NotifyAction,
            "extract_info": ExtractInfoAction,
            "summarize": SummarizeAction,
            "auto_reply": AutoReplyAction,
            "forward": ForwardAction,
            "tag": TagAction,
            "move_to_folder": MoveToFolderAction,
            "check_duplicate": CheckDuplicateAction,
            "save_attachment": SaveAttachmentAction,
            "save_record": SaveRecordAction,
            "http_request": HttpRequestAction,
            "set_variable": SetVariableAction,
            "log": LogAction,
            "execute_script": ExecuteScriptAction,
        }

    # ------------------------------------------------------------------
    # 步骤分发
    # ------------------------------------------------------------------
    def execute_step(self, step: dict, ctx: WorkflowContext) -> Any:
        """执行单个步骤。

        Args:
            step: 步骤定义字典。
            ctx: 流程上下文。

        Returns:
            - action 步骤: Action 的输出值
            - condition 步骤: {"goto": step_id}
            - switch 步骤: {"goto": step_id}
            - loop 步骤: 子步骤结果列表
        """
        step_type = step.get("type", "action")
        if step_type == "condition":
            return self._execute_condition(step, ctx)
        if step_type == "switch":
            return self._execute_switch(step, ctx)
        if step_type == "loop":
            return self._execute_loop(step, ctx)
        # 默认按 action 处理
        return self._execute_action(step, ctx)

    # ------------------------------------------------------------------
    # action 步骤
    # ------------------------------------------------------------------
    def _execute_action(self, step: dict, ctx: WorkflowContext) -> Any:
        action_name = step.get("action")
        if not action_name:
            raise ValueError(f"步骤缺少 action 字段: {step.get('id', '')}")
        action_cls = self._action_classes.get(action_name)
        if action_cls is None:
            raise ValueError(f"未知 action: {action_name}")

        config = self._resolve_config(step.get("config", {}), ctx)
        on_error = step.get("on_error", "skip")
        action = action_cls(ctx=ctx, config=config, logger=logger)
        action.dependencies = self.deps

        return self._execute_with_retry(action, on_error, step.get("id", ""))

    def _execute_with_retry(
        self, action: BaseAction, on_error: str, step_id: str
    ) -> Any:
        """按 on_error 策略执行 action。"""
        on_error = (on_error or "skip").lower()

        # 无重试策略
        if on_error in ("skip", "continue", "abort"):
            try:
                return action.execute()
            except Exception as exc:
                if on_error == "abort":
                    raise
                logger.warning(f"步骤 {step_id} action {action.action_name} 执行失败 (跳过): {exc}")
                return None

        # 带重试策略
        if on_error in ("retry_then_skip", "retry_then_abort"):
            last_exc: Exception | None = None
            for attempt in range(_DEFAULT_MAX_RETRIES):
                try:
                    return action.execute()
                except Exception as exc:
                    last_exc = exc
                    logger.warning(
                        f"步骤 {step_id} action {action.action_name} "
                        f"第 {attempt + 1}/{_DEFAULT_MAX_RETRIES} 次重试失败: {exc}"
                    )
                    if attempt < _DEFAULT_MAX_RETRIES - 1:
                        time.sleep(_RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)])
            if on_error == "retry_then_abort":
                raise last_exc  # type: ignore[misc]
            logger.warning(
                f"步骤 {step_id} action {action.action_name} 重试 "
                f"{_DEFAULT_MAX_RETRIES} 次后跳过"
            )
            return None

        # 未知策略按 skip 处理
        logger.warning(f"步骤 {step_id} 未知 on_error 策略 {on_error!r}，按 skip 处理")
        try:
            return action.execute()
        except Exception as exc:
            logger.warning(f"步骤 {step_id} action 执行失败 (跳过): {exc}")
            return None

    # ------------------------------------------------------------------
    # condition 步骤
    # ------------------------------------------------------------------
    def _execute_condition(self, step: dict, ctx: WorkflowContext) -> dict:
        expr = step.get("condition", "")
        result = evaluate_condition(expr, ctx)
        goto = step.get("if_true") if result else step.get("if_false")
        logger.info(
            f"condition 步骤 {step.get('id', '')} 求值={result} goto={goto}"
        )
        return {"goto": goto}

    # ------------------------------------------------------------------
    # switch 步骤
    # ------------------------------------------------------------------
    def _execute_switch(self, step: dict, ctx: WorkflowContext) -> dict:
        field_path = step.get("field", "")
        field_value = ctx.get(field_path) if field_path else None
        cases = step.get("cases", []) or []
        for case in cases:
            case_value = case.get("value")
            if isinstance(case_value, list):
                if field_value in case_value:
                    return {"goto": case.get("goto")}
            elif field_value == case_value:
                return {"goto": case.get("goto")}
        return {"goto": step.get("default")}

    # ------------------------------------------------------------------
    # loop 步骤
    # ------------------------------------------------------------------
    def _execute_loop(self, step: dict, ctx: WorkflowContext) -> list:
        items_path = step.get("items", "")
        items = ctx.get(items_path) if items_path else []
        if items is None:
            items = []
        if not isinstance(items, (list, tuple)):
            logger.warning(
                f"loop 步骤 {step.get('id', '')} items 不是列表: {type(items).__name__}"
            )
            items = [items]

        item_var = step.get("item_var", "item")
        sub_steps = step.get("steps", []) or []
        results: list = []
        for item in items:
            ctx.set(f"variables.{item_var}", item)
            for sub_step in sub_steps:
                result = self.execute_step(sub_step, ctx)
                results.append(result)
                # 子步骤的 output 别名也写入 ctx
                output_alias = sub_step.get("output")
                if output_alias and result is not None:
                    ctx.set_step_output(
                        sub_step.get("id", ""), output_alias, result
                    )
        return results

    # ------------------------------------------------------------------
    # config 变量解析
    # ------------------------------------------------------------------
    def _resolve_config(self, config: Any, ctx: WorkflowContext) -> Any:
        """递归解析 config 中的 ${...} 变量引用。

        - 整串为单个 ${...} 时返回原始值（保留类型）
        - 否则做字符串替换（值转 str）
        """
        if isinstance(config, dict):
            return {k: self._resolve_config(v, ctx) for k, v in config.items()}
        if isinstance(config, list):
            return [self._resolve_config(v, ctx) for v in config]
        if isinstance(config, str):
            return self._resolve_string(config, ctx)
        return config

    def _resolve_string(self, s: str, ctx: WorkflowContext) -> Any:
        if "${" not in s:
            return s
        # 整串为单个变量引用 → 保留原值类型
        if _FULL_VAR_PATTERN.match(s):
            return ctx.get(s)
        # 混合字符串 → 字符串替换
        def replace(match: re.Match) -> str:
            value = ctx.get(match.group(0))
            if value is None:
                return ""
            return str(value)

        return _VAR_PATTERN.sub(replace, s)
