"""密钥安全管理模块

使用 cryptography 库的 Fernet 对称加密对敏感信息进行加密存储。
密钥通过 PBKDF2-HMAC-SHA256 基于机器特征（hostname + username）派生，
salt 固定，加密后写入 config/secrets.enc，Linux 下文件权限设为 0600。

明文内部结构::

    {
        "accounts": {"default": "pwd"},
        "api_keys": {"deepseek": "sk-xxx"},
        "webhooks": {"wecom": "url"}
    }
"""

from __future__ import annotations

import base64
import getpass
import json
import os
import platform
import re
import socket
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# 固定 salt（16 字节），用于 PBKDF2 密钥派生
_FIXED_SALT: bytes = b"email_helper_v1_"
# PBKDF2 迭代次数
_PBKDF2_ITERATIONS: int = 100_000
# 派生密钥长度（Fernet 要求 32 字节）
_DERIVED_KEY_LENGTH: int = 32

# 模板引用正则：${secrets.xxx.yyy}
_SECRET_REF_PATTERN: re.Pattern[str] = re.compile(r"\$\{secrets\.([^}]+)\}")


def _derive_fernet_key() -> bytes:
    """基于机器特征派生 Fernet 密钥。

    使用 PBKDF2-HMAC-SHA256 算法，passphrase 为 hostname + username 组合，
    salt 固定。返回 base64-urlsafe 编码的 32 字节密钥，可直接传给 Fernet。

    Returns:
        base64-urlsafe 编码的 Fernet 密钥
    """
    hostname = socket.gethostname() or "unknown_host"
    try:
        username = getpass.getuser() or "unknown_user"
    except Exception:
        username = (
            os.environ.get("USER")
            or os.environ.get("USERNAME")
            or "unknown_user"
        )

    passphrase = f"{hostname}|{username}".encode("utf-8")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_DERIVED_KEY_LENGTH,
        salt=_FIXED_SALT,
        iterations=_PBKDF2_ITERATIONS,
    )
    derived = kdf.derive(passphrase)
    return base64.urlsafe_b64encode(derived)


class SecretManager:
    """密钥管理器。

    负责账户密码、API Key、Webhook URL 等敏感信息的加密存储与访问。
    使用 Fernet 对称加密，密钥由机器特征派生，确保同一机器可解密，
    不同机器无法读取。内存缓存 ``_secrets_cache`` 避免频繁解密。
    """

    def __init__(self, secrets_path: Path) -> None:
        """初始化密钥管理器。

        如果 secrets.enc 不存在则创建空存储；存在则加载解密到内存缓存。

        Args:
            secrets_path: secrets.enc 文件路径
        """
        self._secrets_path: Path = Path(secrets_path)
        self._fernet: Fernet = Fernet(_derive_fernet_key())
        # 内存缓存，避免频繁解密
        self._secrets_cache: dict[str, Any] = {
            "accounts": {},
            "api_keys": {},
            "webhooks": {},
        }
        self._loaded: bool = False
        # 启动时自动加载
        self.load()

    def load(self) -> None:
        """从 secrets.enc 加载并解密到内存缓存。

        文件不存在时初始化为空结构并保存；文件存在但解密失败
        （如机器特征变化）时重置为空缓存，不抛出异常。
        """
        empty_cache: dict[str, Any] = {
            "accounts": {},
            "api_keys": {},
            "webhooks": {},
        }

        if not self._secrets_path.exists():
            # 文件不存在，初始化为空并保存
            self._secrets_cache = empty_cache
            self._loaded = True
            self.save()
            return

        try:
            encrypted = self._secrets_path.read_bytes()
            if not encrypted:
                self._secrets_cache = empty_cache
                self._loaded = True
                return

            plaintext = self._fernet.decrypt(encrypted)
            data = json.loads(plaintext.decode("utf-8"))
            # 规范化结构，确保三个顶层 key 存在且为 dict
            self._secrets_cache = {
                "accounts": data.get("accounts", {})
                if isinstance(data.get("accounts"), dict)
                else {},
                "api_keys": data.get("api_keys", {})
                if isinstance(data.get("api_keys"), dict)
                else {},
                "webhooks": data.get("webhooks", {})
                if isinstance(data.get("webhooks"), dict)
                else {},
            }
            self._loaded = True
        except (InvalidToken, json.JSONDecodeError, ValueError):
            # 解密失败（机器变化/文件损坏）：重置为空缓存
            self._secrets_cache = empty_cache
            self._loaded = True

    def save(self) -> None:
        """将内存缓存加密后写入 secrets.enc。

        使用临时文件 + 原子替换避免写入中断导致文件损坏。
        Linux 下设置文件权限为 0600（仅所有者可读写）。
        """
        plaintext = json.dumps(
            self._secrets_cache, ensure_ascii=False
        ).encode("utf-8")
        encrypted = self._fernet.encrypt(plaintext)

        # 确保父目录存在
        self._secrets_path.parent.mkdir(parents=True, exist_ok=True)
        # 写入临时文件再原子替换，避免写入中断损坏
        tmp_path = self._secrets_path.with_suffix(".enc.tmp")
        tmp_path.write_bytes(encrypted)
        tmp_path.replace(self._secrets_path)

        # Linux 下设置 0600 权限
        if platform.system() == "Linux":
            try:
                os.chmod(self._secrets_path, 0o600)
            except OSError:
                pass

    @staticmethod
    def _normalize_path(path: str) -> str:
        """规范化路径，去除可选的 ``secrets.`` 前缀。

        同时支持 ``"accounts.default"`` 和 ``"secrets.accounts.default"``
        两种写法。

        Args:
            path: 点号分隔的路径

        Returns:
            去除前缀后的路径
        """
        if path.startswith("secrets."):
            return path[len("secrets."):]
        return path

    def _navigate(
        self, path: str, create: bool = False
    ) -> tuple[dict, str] | None:
        """按点号分隔的路径导航到目标字典和最终键名。

        Args:
            path: 点号分隔路径，如 ``"accounts.default"``
            create: 是否自动创建中间字典

        Returns:
            ``(父字典, 最后一段键名)`` 元组；路径无效时返回 None
        """
        if not path:
            return None
        parts = path.split(".")
        if len(parts) < 2:
            return None

        current: Any = self._secrets_cache
        for part in parts[:-1]:
            if not isinstance(current, dict):
                return None
            if part not in current:
                if create:
                    current[part] = {}
                else:
                    return None
            current = current[part]

        if not isinstance(current, dict):
            return None
        return current, parts[-1]

    def set_secret(self, path: str, value: str) -> None:
        """设置密钥值并立即保存。

        Args:
            path: 点号分隔路径，如 ``"accounts.default"`` /
                  ``"api_keys.deepseek"`` / ``"webhooks.wecom"``
            value: 密钥明文值
        """
        normalized = self._normalize_path(path)
        result = self._navigate(normalized, create=True)
        if result is None:
            return
        parent, key = result
        parent[key] = value
        self.save()

    def get_secret(self, path: str) -> str | None:
        """获取密钥值。

        Args:
            path: 点号分隔路径，如 ``"accounts.default"``

        Returns:
            密钥明文值；不存在时返回 None
        """
        normalized = self._normalize_path(path)
        result = self._navigate(normalized, create=False)
        if result is None:
            return None
        parent, key = result
        value = parent.get(key)
        return value if isinstance(value, str) else None

    def has_secret(self, path: str) -> bool:
        """判断密钥是否存在。

        Args:
            path: 点号分隔路径

        Returns:
            存在返回 True，否则 False
        """
        return self.get_secret(path) is not None

    def delete_secret(self, path: str) -> None:
        """删除密钥并立即保存。

        Args:
            path: 点号分隔路径
        """
        normalized = self._normalize_path(path)
        result = self._navigate(normalized, create=False)
        if result is None:
            return
        parent, key = result
        if key in parent:
            del parent[key]
            self.save()

    def resolve_template(self, template: str) -> str:
        """解析密钥引用模板。

        将形如 ``"${secrets.accounts.default}"`` 的引用替换为实际密钥值。
        支持字符串中嵌入多个引用。引用无法解析时替换为空字符串。

        Args:
            template: 包含密钥引用的模板字符串

        Returns:
            替换后的字符串；不含引用则原样返回
        """
        if not isinstance(template, str) or "${secrets." not in template:
            return template  # type: ignore[return-value]

        def _replace(match: re.Match[str]) -> str:
            secret_path = match.group(1)
            value = self.get_secret(secret_path)
            return value if value is not None else ""

        return _SECRET_REF_PATTERN.sub(_replace, template)
