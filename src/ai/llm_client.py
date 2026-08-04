"""LLM API 客户端模块

统一封装 DeepSeek / OpenAI / Ollama 三种后端的对话调用。
使用 requests 库直连 HTTP 接口，不依赖 openai SDK。
"""

import time
from typing import Any

import requests

from src.core.logger import get_logger

logger = get_logger("ai.llm_client")


class LLMClient:
    """LLM API 客户端，支持 deepseek / openai / ollama 三种 provider"""

    def __init__(
        self,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 500,
        timeout: int = 30,
    ) -> None:
        """初始化 LLM 客户端

        Args:
            provider: 后端类型，deepseek / openai / ollama
            api_key: API 密钥（ollama 可传空字符串）
            base_url: 服务地址。
                deepseek/openai: 如 https://api.deepseek.com
                ollama: 如 http://localhost:11434
            model: 模型名称
            temperature: 采样温度，默认 0.1（低温度保证分类稳定性）
            max_tokens: 最大输出 token 数
            timeout: 请求超时秒数
        """
        provider = (provider or "").lower()
        if provider not in ("deepseek", "openai", "ollama"):
            raise ValueError(f"不支持的 provider: {provider}")
        self.provider: str = provider
        self.api_key: str = api_key or ""
        self.base_url: str = (base_url or "").rstrip("/")
        self.model: str = model
        self.temperature: float = temperature
        self.max_tokens: int = max_tokens
        self.timeout: int = timeout

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM API，返回文本响应

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入提示词

        Returns:
            LLM 输出的纯文本响应

        Raises:
            requests.RequestException: 网络/超时/认证/限流等失败时抛出
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if self.provider == "ollama":
            url = f"{self.base_url}/api/chat"
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": self.temperature},
            }
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            # deepseek / openai 兼容 OpenAI 接口
            url = f"{self.base_url}/v1/chat/completions"
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

        logger.info(
            f"调用 LLM: provider={self.provider}, model={self.model}, endpoint={url}"
        )
        start = time.time()
        try:
            resp = requests.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )
            resp.raise_for_status()
        except requests.Timeout:
            logger.error(f"LLM 调用超时 ({self.timeout}s), endpoint={url}")
            raise
        except requests.RequestException as e:
            logger.error(f"LLM 调用失败: {e}")
            raise

        elapsed = time.time() - start
        data = resp.json()

        if self.provider == "ollama":
            content = (data.get("message") or {}).get("content", "")
        else:
            choices = data.get("choices") or []
            if not choices:
                logger.warning(f"LLM 响应无 choices: {str(data)[:200]}")
                content = ""
            else:
                content = (choices[0].get("message") or {}).get("content", "")

        # 绝不记录敏感内容，仅截断预览
        preview = content[:200].replace("\n", " ")
        logger.info(
            f"LLM 响应耗时 {elapsed:.2f}s, 内容长度 {len(content)}, 预览: {preview}"
        )
        return content

    def test_connection(self) -> bool:
        """测试连接是否正常

        Returns:
            连接成功返回 True，失败返回 False
        """
        try:
            self.chat("You are a connection test assistant.", "ping")
            return True
        except Exception as e:
            logger.warning(f"LLM 连接测试失败: {e}")
            return False
