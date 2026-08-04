"""记录日志 Action：按指定级别写一条流程日志。"""

from __future__ import annotations

from typing import Any

from src.workflow.actions.base import BaseAction


class LogAction(BaseAction):
    """按级别记录日志消息。"""

    action_name = "log"

    _LEVEL_MAP = {
        "DEBUG": "debug",
        "INFO": "info",
        "WARNING": "warning",
        "WARN": "warning",
        "ERROR": "error",
        "CRITICAL": "critical",
    }

    def execute(self) -> Any:
        level = str(self.config.get("level", "INFO")).upper()
        message = self.config.get("message", "")
        log_fn_name = self._LEVEL_MAP.get(level, "info")
        getattr(self.logger, log_fn_name)(message)
        return {"logged": True, "level": level, "message": message}
