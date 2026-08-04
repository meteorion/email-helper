"""通知重试处理器"""

import random

from src.core.logger import get_logger

logger = get_logger("notification.retry")


class RetryHandler:
    """重试处理器

    指数退避: 5s → 15s → 45s (base_delay * backoff_multiplier^attempt)
    错误分类:
      - network/timeout/rate_limit → 可重试
      - invalid_param/auth_failed   → 不重试
    企微 45009 频率限制错误 → 固定等待 60 秒
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 5.0,
        backoff_multiplier: float = 3.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_multiplier = backoff_multiplier

    def should_retry(self, error: str) -> bool:
        """判断错误是否可重试

        network/timeout/rate_limit 可重试, invalid_param/auth_failed 不重试
        """
        e = error.lower()
        if "network" in e or "timeout" in e or "rate_limit" in e:
            return True
        return False

    def get_delay(self, attempt: int) -> float:
        """计算指数退避延迟

        5s → 15s → 45s, 加 ±10% 抖动
        """
        delay = self.base_delay * (self.backoff_multiplier ** attempt)
        jitter = random.uniform(-0.1, 0.1) * delay
        return delay + jitter

    def is_rate_limit_error(self, error: str) -> bool:
        """判断是否为企微 45009 频率限制错误

        企微 45009 错误码 → 固定等待 60 秒
        """
        return "45009" in error
