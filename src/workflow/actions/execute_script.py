"""执行自定义脚本 Action：用 subprocess 运行 Python 脚本，超时 30s。"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from src.workflow.actions.base import BaseAction


class ExecuteScriptAction(BaseAction):
    """执行自定义 Python 脚本，返回 returncode / stdout / stderr。"""

    action_name = "execute_script"

    def execute(self) -> Any:
        script_path = self.config.get("script_path")
        if not script_path:
            raise ValueError("execute_script 缺少 script_path")
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"脚本不存在: {script_path}")

        args = self.config.get("args", []) or []
        env_extra = self.config.get("env", {}) or {}
        timeout = self.config.get("timeout", 30)
        python_executable = self.config.get("python", "python")

        cmd = [python_executable, script_path] + [str(a) for a in args]
        process_env = dict(os.environ)
        process_env.update({k: str(v) for k, v in env_extra.items()})

        self.logger.info(f"执行脚本: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=process_env,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"脚本执行超时 ({timeout}s): {script_path}")

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
