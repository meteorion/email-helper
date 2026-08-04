"""设置变量 Action：把值写入流程上下文的 variables 命名空间。"""

from __future__ import annotations

from typing import Any

from src.workflow.actions.base import BaseAction


class SetVariableAction(BaseAction):
    """设置流程变量，后续步骤可通过 ${variables.xxx} 引用。"""

    action_name = "set_variable"

    def execute(self) -> Any:
        name = self.config.get("name")
        if not name:
            raise ValueError("set_variable 缺少 name")
        value = self.config.get("value")
        self.ctx.set(f"variables.{name}", value)
        self.logger.info(f"流程变量已设置: {name}={value!r}")
        return {"name": name, "value": value}
