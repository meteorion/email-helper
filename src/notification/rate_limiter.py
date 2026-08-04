"""令牌桶限流器"""

import threading
import time

from src.core.logger import get_logger

logger = get_logger("notification.rate_limiter")


class TokenBucket:
    """令牌桶限流器（线程安全）

    默认 capacity=20, refill_interval_ms=3000（每 3 秒补充 1 个令牌，上限 20），
    符合企微 20 条/分钟限制。
    """

    def __init__(self, capacity: int = 20, refill_interval_ms: int = 3000):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_interval = refill_interval_ms / 1000.0
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def acquire(self, timeout: float | None = None) -> bool:
        """获取令牌，返回是否成功

        流程:
          1. 先 _refill() 补充令牌
          2. 有令牌 → 扣减并 return True
          3. 没令牌 → 等下一次 refill，最多等待 timeout 秒
          4. wait_time = max(0, ...) 防负值
        """
        start_time = time.time()
        while True:
            with self._lock:
                self._refill()
                if self.tokens >= 1:
                    self.tokens -= 1
                    return True
                wait_time = max(
                    0.0,
                    self.refill_interval - (time.time() - self.last_refill),
                )

            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    return False

            time.sleep(min(wait_time, 0.1))

    def _refill(self) -> None:
        """根据时间差补充令牌（需在锁内调用）"""
        now = time.time()
        elapsed = now - self.last_refill
        if elapsed >= self.refill_interval:
            new_tokens = int(elapsed / self.refill_interval)
            self.tokens = min(float(self.capacity), self.tokens + new_tokens)
            # 仅推进已消耗的完整周期，保留小数部分（更精确）
            self.last_refill += new_tokens * self.refill_interval
