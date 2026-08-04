"""Action 基类

所有内置 Action 继承 BaseAction，由 StepExecutor 实例化并注入：
- ctx: WorkflowContext
- config: 已解析变量引用后的步骤配置字典
- logger: 日志器
- dependencies: 引擎注入的依赖字典（notification_engine / llm_client / ...）
"""

from __future__ import annotations

from typing import Any

from src.workflow.context import WorkflowContext


class BaseAction:
    """所有 Action 的基类，子类需实现 execute() 方法。"""

    action_name: str = ""

    def __init__(self, ctx: WorkflowContext, config: dict, logger):
        """初始化 Action。

        Args:
            ctx: 流程上下文。
            config: 步骤 config 字典（变量引用已被执行器解析）。
            logger: 日志器实例。
        """
        self.ctx = ctx
        self.config: dict = config or {}
        self.logger = logger
        # 依赖字典，由 StepExecutor 在创建实例后注入
        self.dependencies: dict = {}

    def execute(self) -> Any:
        """执行 Action，返回输出值（写入 ctx 的 step_output）。"""
        raise NotImplementedError(f"Action {self.action_name} 未实现 execute()")

    # ------------------------------------------------------------------
    # 依赖访问辅助
    # ------------------------------------------------------------------
    def _dep(self, name: str) -> Any:
        """按名称取依赖，缺失时返回 None。"""
        return self.dependencies.get(name)

    def _require_dep(self, name: str) -> Any:
        """按名称取依赖，缺失时抛 RuntimeError。"""
        dep = self.dependencies.get(name)
        if dep is None:
            raise RuntimeError(f"Action {self.action_name} 缺少依赖: {name}")
        return dep

    def _mail(self):
        """便捷获取当前邮件对象。"""
        return self.ctx.mail
