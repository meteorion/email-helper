"""日志脱敏过滤器模块

提供 LogSanitizer 工具类和 SanitizeFilter 日志过滤器，自动识别并脱敏
日志中的敏感信息，包括：

- password / api_key / secret / token 等字段值
- ``sk-`` 开头的 API Key
- Webhook URL 中 ``?key=xxx`` 部分
- base64 编码的密码字符串（长度 > 20）
"""

from __future__ import annotations

import logging
import re
from typing import Any

# 敏感字段名（不区分大小写）
_SENSITIVE_FIELDS: str = (
    r"password|passwd|pwd|api_key|apikey|secret|token|access_token|refresh_token"
)

# 模式 1：字段值脱敏
# 匹配 password=xxx / "password": "xxx" / api_key: xxx 等形式
# \b 确保匹配完整字段名，\1 和 \4 为引号回溯引用
_FIELD_VALUE_PATTERN: re.Pattern[str] = re.compile(
    rf'(?i)(["\']?)(\b(?:{_SENSITIVE_FIELDS})\b)\1(\s*[:=]\s*)'
    rf'(["\']?)([^\s,}}\]"\']+)\4'
)

# 模式 2：sk- 开头的 API Key（OpenAI / DeepSeek 风格）
_SK_KEY_PATTERN: re.Pattern[str] = re.compile(r"sk-[A-Za-z0-9_-]+")

# 模式 3：Webhook URL 中 ?key=xxx 部分
_WEBHOOK_KEY_PATTERN: re.Pattern[str] = re.compile(r"\?[Kk]ey=[^&\s\"']+")

# 模式 4：base64 编码字符串（长度 > 20），可能为编码后的密码
_BASE64_PATTERN: re.Pattern[str] = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")

# 敏感键名匹配（用于 sanitize_dict 的键名检测，子串匹配）
_SENSITIVE_KEY_PATTERN: re.Pattern[str] = re.compile(
    rf"(?i)(?:{_SENSITIVE_FIELDS})"
)


class LogSanitizer:
    """日志脱敏工具类。

    提供静态方法对文本和字典数据进行脱敏处理，所有敏感内容
    替换为 ``***``。
    """

    @staticmethod
    def sanitize(text: str) -> str:
        """对文本进行脱敏处理。

        依次应用四类正则模式，将匹配的敏感内容替换为 ``***``：

        1. password/api_key/secret/token 等字段值
        2. ``sk-`` 开头的 API Key → ``sk-***``
        3. Webhook URL 中 ``?key=xxx`` → ``?key=***``
        4. 长度 > 20 的 base64 字符串 → ``***``

        Args:
            text: 待脱敏的文本

        Returns:
            脱敏后的文本；输入非字符串时原样返回
        """
        if not isinstance(text, str) or not text:
            return text  # type: ignore[return-value]

        # 模式 1：字段值脱敏，保留字段名，仅替换值
        def _replace_field(match: re.Match[str]) -> str:
            opening_quote = match.group(1)  # 字段名前引号
            field_name = match.group(2)  # 字段名
            separator = match.group(3)  # 分隔符（: 或 =）
            value_quote = match.group(4)  # 值前引号
            return f"{opening_quote}{field_name}{opening_quote}{separator}{value_quote}***{value_quote}"

        result = _FIELD_VALUE_PATTERN.sub(_replace_field, text)

        # 模式 2：sk- 开头的 API Key
        result = _SK_KEY_PATTERN.sub("sk-***", result)

        # 模式 3：Webhook URL 中 ?key=xxx
        result = _WEBHOOK_KEY_PATTERN.sub("?key=***", result)

        # 模式 4：base64 编码字符串（长度 > 20）
        result = _BASE64_PATTERN.sub("***", result)

        return result

    @staticmethod
    def sanitize_dict(data: Any) -> Any:
        """递归脱敏字典数据。

        遍历字典/列表/标量，对键名包含敏感关键词的字符串值替换为 ``***``，
        对其他字符串值调用 :meth:`sanitize` 进行模式匹配脱敏。

        Args:
            data: 待脱敏的数据（dict / list / str / 其他）

        Returns:
            脱敏后的数据（结构与输入一致）
        """
        if isinstance(data, dict):
            result: dict[Any, Any] = {}
            for key, value in data.items():
                key_str = str(key)
                if isinstance(value, str) and _SENSITIVE_KEY_PATTERN.search(
                    key_str
                ):
                    # 键名包含敏感关键词，直接替换值为 ***
                    result[key] = "***"
                else:
                    result[key] = LogSanitizer.sanitize_dict(value)
            return result
        elif isinstance(data, list):
            return [LogSanitizer.sanitize_dict(item) for item in data]
        elif isinstance(data, str):
            return LogSanitizer.sanitize(data)
        else:
            return data


class SanitizeFilter(logging.Filter):
    """日志脱敏过滤器。

    继承 :class:`logging.Filter`，注册到 logging handler 后，
    对每条日志记录的消息进行自动脱敏。脱敏失败时不阻塞日志输出。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """对日志记录进行脱敏处理。

        将格式化后的消息替换为脱敏版本，并清除 args 避免二次格式化。
        脱敏过程出错时保留原始记录，始终返回 True（不丢弃日志）。

        Args:
            record: 日志记录对象

        Returns:
            始终返回 True（允许记录通过）
        """
        try:
            formatted = record.getMessage()
            record.msg = LogSanitizer.sanitize(formatted)
            record.args = None
        except Exception:
            # 脱敏失败不阻塞日志输出
            pass
        return True
