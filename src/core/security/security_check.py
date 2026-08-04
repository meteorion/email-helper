"""启动安全检查模块

在程序启动时执行一系列安全检查，返回检查结果列表。
每项结果为 ``{"check": 名称, "severity": 级别, "message": 消息}``，
级别包括 ``HIGH``（高危）、``WARN``（警告）、``NONE``（无问题）。

检查项：

1. ``check_secrets_file_permissions`` — Linux 下 secrets.enc 权限须为 0600
2. ``check_no_plaintext_secrets`` — 扫描 config/*.json 有无明文 password
3. ``check_ssl_enforcement`` — IMAP/SMTP 配置必须 SSL=True
"""

from __future__ import annotations

import json
import platform
import re
from pathlib import Path
from typing import Callable

from src.core.logger import get_logger

logger = get_logger("security.check")

# 默认 secrets.enc 路径
_DEFAULT_SECRETS_PATH: Path = Path("config/secrets.enc")
# 默认 config 目录
_DEFAULT_CONFIG_DIR: Path = Path("config")

# 明文密码检测正则
# 匹配 password/passwd/pwd 字段后跟 : 或 = 的值，排除 secrets. 引用格式
# (?<![a-zA-Z]) 确保不匹配 mypassword 等包含 password 的更大单词
_PLAINTEXT_PASSWORD_PATTERN: re.Pattern[str] = re.compile(
    r"""(?i)(?<![a-zA-Z])(?:password|passwd|pwd)["']?\s*[:=]\s*"""
    r"""["']?(?!secrets\.)([^"'\s,}]+)["']?"""
)


def check_secrets_file_permissions(
    secrets_path: Path = _DEFAULT_SECRETS_PATH,
) -> dict:
    """检查 secrets.enc 文件权限（Linux 下应为 0600）。

    Args:
        secrets_path: secrets.enc 文件路径

    Returns:
        检查结果字典
    """
    if platform.system() != "Linux":
        return {
            "check": "secrets_file_permissions",
            "severity": "NONE",
            "message": "非 Linux 系统，跳过权限检查",
        }

    if not secrets_path.exists():
        return {
            "check": "secrets_file_permissions",
            "severity": "NONE",
            "message": "secrets.enc 不存在，无需检查权限",
        }

    try:
        file_stat = secrets_path.stat()
        mode = file_stat.st_mode & 0o777
        if mode != 0o600:
            return {
                "check": "secrets_file_permissions",
                "severity": "HIGH",
                "message": f"secrets.enc 权限为 {oct(mode)}，应为 0600"
                f"（仅所有者可读写）",
            }
        return {
            "check": "secrets_file_permissions",
            "severity": "NONE",
            "message": "secrets.enc 权限正确 (0600)",
        }
    except OSError as e:
        return {
            "check": "secrets_file_permissions",
            "severity": "WARN",
            "message": f"无法读取 secrets.enc 权限: {e}",
        }


def check_no_plaintext_secrets(
    config_dir: Path = _DEFAULT_CONFIG_DIR,
) -> dict:
    """扫描 config/*.json 配置文件，检测明文密码字段。

    排除 ``${secrets.xxx}`` 引用格式和空值。

    Args:
        config_dir: 配置目录

    Returns:
        检查结果字典
    """
    if not config_dir.exists():
        return {
            "check": "no_plaintext_secrets",
            "severity": "NONE",
            "message": "配置目录不存在",
        }

    findings: list[str] = []
    for json_file in config_dir.glob("*.json"):
        try:
            content = json_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # 检测明文 password 字段（排除 secrets. 引用）
        matches = _PLAINTEXT_PASSWORD_PATTERN.findall(content)
        real_matches = [m for m in matches if m and not m.startswith("${")]
        if real_matches:
            findings.append(
                f"{json_file.name}: 发现 {len(real_matches)} 处明文密码"
            )

    if findings:
        return {
            "check": "no_plaintext_secrets",
            "severity": "HIGH",
            "message": "; ".join(findings),
        }
    return {
        "check": "no_plaintext_secrets",
        "severity": "NONE",
        "message": "未发现明文密码",
    }


def check_ssl_enforcement(config_dir: Path = _DEFAULT_CONFIG_DIR) -> dict:
    """检查 IMAP/SMTP 配置是否强制启用 SSL。

    扫描 config/*.json 中的 imap / smtp 配置段，确保 ssl=true。

    Args:
        config_dir: 配置目录

    Returns:
        检查结果字典
    """
    if not config_dir.exists():
        return {
            "check": "ssl_enforcement",
            "severity": "NONE",
            "message": "配置目录不存在",
        }

    findings: list[str] = []
    for json_file in config_dir.glob("*.json"):
        try:
            content = json_file.read_text(encoding="utf-8")
            data = json.loads(content)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue

        if not isinstance(data, dict):
            continue

        # 检查 imap.ssl 和 smtp.ssl
        for section in ("imap", "smtp"):
            section_data = data.get(section)
            if isinstance(section_data, dict) and "ssl" in section_data:
                if not section_data.get("ssl", True):
                    findings.append(
                        f"{json_file.name}: {section}.ssl=False 未启用加密"
                    )

    if findings:
        return {
            "check": "ssl_enforcement",
            "severity": "HIGH",
            "message": "; ".join(findings),
        }
    return {
        "check": "ssl_enforcement",
        "severity": "NONE",
        "message": "IMAP/SMTP 均启用 SSL",
    }


def run_security_checks() -> list[dict]:
    """执行启动安全检查。

    依次运行所有检查项，收集结果并记录日志。
    HIGH 级别记 ERROR 日志，WARN 级别记 WARNING 日志，
    NONE 级别记 INFO 日志。单项检查异常不影响其他检查。

    Returns:
        检查结果列表，每项格式::

            {"check": "检查名称", "severity": "HIGH/WARN/NONE", "message": "消息"}
    """
    checks: list[Callable[[], dict]] = [
        check_secrets_file_permissions,
        check_no_plaintext_secrets,
        check_ssl_enforcement,
    ]

    results: list[dict] = []
    for check_fn in checks:
        try:
            result = check_fn()
            results.append(result)
            severity = result.get("severity", "NONE")
            message = result.get("message", "")
            check_name = result.get("check", "")
            if severity == "HIGH":
                logger.error(f"[安全检查] {check_name}: {message}")
            elif severity == "WARN":
                logger.warning(f"[安全检查] {check_name}: {message}")
            else:
                logger.info(f"[安全检查] {check_name}: {message}")
        except Exception as e:
            # 单项检查异常不影响其他检查
            result = {
                "check": getattr(check_fn, "__name__", "unknown"),
                "severity": "WARN",
                "message": f"检查执行异常: {e}",
            }
            results.append(result)
            logger.warning(f"[安全检查] {result['check']} 异常: {e}")

    return results
