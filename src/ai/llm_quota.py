"""LLM 调用配额跟踪模块

提供基于内存计数 + 日期判断的每日 LLM 调用配额跟踪，不需要持久化。
跨天自动重置计数；daily_quota=0 表示不限。
"""

from datetime import date

from src.core.logger import get_logger

logger = get_logger("ai.llm_quota")


class LLMQuotaTracker:
    """LLM 每日调用配额跟踪器（内存计数，跨天自动重置）"""

    def __init__(self, daily_quota: int = 0) -> None:
        """初始化配额跟踪器

        Args:
            daily_quota: 每日调用上限，0 表示不限制
        """
        self.daily_quota: int = daily_quota
        self._today: date = date.today()
        self._count: int = 0

    def check(self) -> bool:
        """检查当前是否还有可用配额

        Returns:
            还有配额返回 True，配额耗尽返回 False；不限配额时恒为 True
        """
        self.reset_if_new_day()
        if self.daily_quota == 0:
            return True
        return self._count < self.daily_quota

    def increment(self) -> None:
        """增加一次调用计数"""
        self.reset_if_new_day()
        self._count += 1
        if self.daily_quota != 0:
            logger.debug(
                f"LLM 调用计数 +1，今日已用 {self._count}/{self.daily_quota}"
            )

    def get_today_count(self) -> int:
        """获取今日已调用次数"""
        self.reset_if_new_day()
        return self._count

    def get_remaining(self) -> int:
        """获取今日剩余配额

        Returns:
            剩余次数；daily_quota=0 时返回 -1 表示不限
        """
        self.reset_if_new_day()
        if self.daily_quota == 0:
            return -1
        return max(0, self.daily_quota - self._count)

    def reset_if_new_day(self) -> None:
        """如果是新的一天，重置计数"""
        today = date.today()
        if today != self._today:
            logger.info(
                f"跨天重置 LLM 配额计数：{self._today} -> {today}，"
                f"昨日用量 {self._count}"
            )
            self._today = today
            self._count = 0
