"""流程上下文 WorkflowContext

负责流程执行过程中的数据容器管理，支持变量引用语法：
- ${mail.xxx} → 邮件字段（body 别名指向 body_text）
- ${classification.xxx} → 分类结果字段
- ${variables.xxx:-default} → 流程变量，支持默认值
- ${output_alias.xxx} → 步骤输出（别名由 step.output 定义）
- ${secrets.xxx} → SecretManager.resolve_template（不写入快照，安全考虑）
"""

from __future__ import annotations

import re
from typing import Any, Optional

from src.core.logger import get_logger

logger = get_logger("workflow.context")

# 变量引用正则：${...}（非贪婪，不含 } 字符）
_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


class WorkflowContext:
    """流程执行上下文，承载邮件、分类结果、流程变量与步骤输出。"""

    def __init__(self, mail, classify_result: dict, variables: dict, secret_mgr):
        """初始化上下文。

        Args:
            mail: MailData 邮件对象（只读）。
            classify_result: 分类结果字典（只读）。
            variables: 流程变量初始字典（可读写）。
            secret_mgr: SecretManager 实例，用于解析 ${secrets.xxx}。
        """
        self.mail = mail
        self.classify_result: dict = classify_result or {}
        self.variables: dict = dict(variables or {})
        self.secret_mgr = secret_mgr
        # 步骤输出：{output_alias: output_value}
        self.step_outputs: dict = {}

    # ------------------------------------------------------------------
    # 取值
    # ------------------------------------------------------------------
    def get(self, path: str) -> Any:
        """按路径取值。

        支持传入带 ${...} 包裹或裸路径两种形式，例如：
            ctx.get("${mail.subject}")
            ctx.get("variables.timeout")
            ctx.get("${variables.timeout:-30}")

        Args:
            path: 变量路径。

        Returns:
            解析后的值；找不到时返回 None（如有默认值则返回默认值）。
        """
        raw = self._strip_wrapper(path)

        # 默认值语法 :- （仅对 None 值生效）
        default: Optional[str] = None
        has_default = False
        if ":-" in raw:
            raw, default = raw.split(":-", 1)
            has_default = True

        namespace, rest = self._split_namespace(raw)

        try:
            if namespace == "mail":
                value = self._get_mail_field(rest)
            elif namespace == "classification":
                value = self._get_nested(self.classify_result, rest)
            elif namespace == "variables":
                value = self.variables.get(rest)
            elif namespace == "secrets":
                value = self._resolve_secret(rest)
            else:
                # 其它命名空间一律视为步骤输出别名
                value = self._get_step_output(namespace, rest)
        except Exception as exc:  # 解析异常不影响主流程
            logger.warning(f"上下文取值异常 path={path}: {exc}")
            value = None

        if value is None and has_default:
            return self._parse_default(default)
        return value

    # ------------------------------------------------------------------
    # 设值
    # ------------------------------------------------------------------
    def set(self, path: str, value: Any) -> None:
        """按路径设置值，目前仅支持 variables 命名空间。"""
        raw = self._strip_wrapper(path)
        namespace, rest = self._split_namespace(raw)
        if namespace == "variables":
            self.variables[rest] = value
            return
        if namespace in ("mail", "classification", "secrets"):
            raise ValueError(f"命名空间 {namespace} 只读，不可设置")
        # 其它命名空间视为步骤输出别名
        self.step_outputs[namespace] = value

    def set_step_output(self, step_id: str, output_alias: str, output: Any) -> None:
        """保存步骤输出到上下文，供后续步骤通过 ${output_alias.xxx} 引用。"""
        if not output_alias:
            logger.warning(f"步骤 {step_id} 未定义 output 别名，跳过输出保存")
            return
        self.step_outputs[output_alias] = output

    # ------------------------------------------------------------------
    # 快照（持久化 / 断点续传）
    # ------------------------------------------------------------------
    def snapshot(self) -> dict:
        """生成可持久化的快照字典。

        注意：secrets 不写入快照（安全考虑），恢复后由外部重新注入 secret_mgr。
        """
        mail_dict = None
        if self.mail is not None:
            if hasattr(self.mail, "to_dict"):
                try:
                    mail_dict = self.mail.to_dict()
                except Exception:
                    mail_dict = None
            elif isinstance(self.mail, dict):
                mail_dict = self.mail
        return {
            "mail": mail_dict,
            "classification": dict(self.classify_result),
            "variables": dict(self.variables),
            "step_outputs": _safe_serialize(self.step_outputs),
        }

    @classmethod
    def from_snapshot(cls, data: dict) -> "WorkflowContext":
        """从快照恢复上下文。

        secret_mgr 需由调用方在恢复后通过属性赋值重新注入。
        """
        from src.core.models import MailData  # 延迟导入避免循环

        mail_data = data.get("mail")
        mail = None
        if isinstance(mail_data, dict):
            try:
                mail = MailData.from_dict(mail_data)
            except Exception as exc:
                logger.warning(f"从快照恢复 MailData 失败: {exc}")
                mail = None
        elif mail_data is not None and hasattr(mail_data, "message_id"):
            mail = mail_data

        ctx = cls(
            mail=mail,
            classify_result=data.get("classification", {}),
            variables=data.get("variables", {}),
            secret_mgr=None,
        )
        ctx.step_outputs = data.get("step_outputs", {}) or {}
        return ctx

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------
    @staticmethod
    def _strip_wrapper(path: str) -> str:
        """去掉 ${...} 包裹，返回内部表达式。"""
        if path.startswith("${") and path.endswith("}"):
            return path[2:-1]
        return path

    @staticmethod
    def _split_namespace(raw: str) -> tuple[str, str]:
        """按第一个点拆分命名空间与剩余路径。"""
        if "." in raw:
            namespace, rest = raw.split(".", 1)
            return namespace, rest
        return raw, ""

    def _get_mail_field(self, field: str) -> Any:
        """读取 mail 字段，body 别名指向 body_text。"""
        if not field:
            return None
        if field == "body":
            field = "body_text"
        if field == "id":
            field = "message_id"
        if field == "has_attachment":
            attachments = getattr(self.mail, "attachments", None) or []
            return len(attachments) > 0
        if field == "attachment_count":
            attachments = getattr(self.mail, "attachments", None) or []
            return len(attachments)
        if field == "attachments":
            attachments = getattr(self.mail, "attachments", None) or []
            result = []
            for att in attachments:
                if hasattr(att, "to_dict"):
                    result.append(att.to_dict())
                elif isinstance(att, dict):
                    result.append(att)
            return result
        value = getattr(self.mail, field, None)
        # datetime 等对象序列化为 ISO 字符串
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return str(value)
        return value

    @staticmethod
    def _get_nested(data: Any, path: str) -> Any:
        """按 a.b.c 路径在 dict 中取值。"""
        if not path:
            return data
        if not isinstance(data, dict):
            return None
        value = data
        for part in path.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _get_step_output(self, alias: str, path: str) -> Any:
        """读取步骤输出，path 支持嵌套字段访问。"""
        if alias not in self.step_outputs:
            return None
        output = self.step_outputs[alias]
        if not path:
            return output
        if isinstance(output, dict):
            return self._get_nested(output, path)
        # 非字典类型但有 path：无法访问
        return None

    def _resolve_secret(self, path: str) -> Any:
        """委托 SecretManager.resolve_template 解析 ${secrets.path}。"""
        if self.secret_mgr is None:
            return None
        resolve = getattr(self.secret_mgr, "resolve_template", None)
        if resolve is None:
            return None
        try:
            return resolve(f"${{secrets.{path}}}")
        except Exception as exc:
            logger.warning(f"解析 secret {path} 失败: {exc}")
            return None

    @staticmethod
    def _parse_default(default: str) -> Any:
        """把默认值字符串解析为合适的 Python 类型。"""
        if default is None:
            return None
        s = default.strip()
        if s.lower() == "true":
            return True
        if s.lower() in ("false",):
            return False
        if s.lower() in ("null", "none", ""):
            return None if s.lower() != "false" else False
        # 去引号
        if len(s) >= 2 and s[0] in "'\"" and s[-1] == s[0]:
            return s[1:-1]
        try:
            return int(s)
        except ValueError:
            pass
        try:
            return float(s)
        except ValueError:
            pass
        return s


def _safe_serialize(obj: Any) -> Any:
    """递归把不可 JSON 序列化的对象转为字符串，保证快照可持久化。"""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(v) for v in obj]
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:
            return str(obj)
    return str(obj)
