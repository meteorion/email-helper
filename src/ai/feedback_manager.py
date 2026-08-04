"""反馈闭环管理器模块

将用户对 AI 分类的修正反馈以 JSON Lines 格式写入 data/feedback/feedback.jsonl，
并提供统计与最近反馈查询能力。
"""

import json
from datetime import datetime
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger("ai.feedback")


class FeedbackManager:
    """分类反馈管理器，写入 JSONL 并提供统计"""

    def __init__(self, feedback_dir: Path) -> None:
        """初始化反馈管理器

        Args:
            feedback_dir: 反馈数据目录，如 data/feedback/
        """
        self.feedback_dir: Path = Path(feedback_dir)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_file: Path = self.feedback_dir / "feedback.jsonl"

    def record_feedback(
        self,
        mail_message_id: str,
        original_category: str,
        corrected_category: str,
        reason: str = "",
    ) -> None:
        """记录一条分类修正反馈

        Args:
            mail_message_id: 邮件 message_id
            original_category: 原始分类
            corrected_category: 修正后的分类
            reason: 修正原因（可选）
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "mail_message_id": mail_message_id,
            "original_category": original_category,
            "corrected_category": corrected_category,
            "reason": reason,
        }
        try:
            with open(self.feedback_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.info(
                f"记录反馈: mail={mail_message_id}, "
                f"{original_category} -> {corrected_category}"
            )
        except Exception as e:
            logger.error(f"写入反馈记录失败: {e}")

    def get_feedback_stats(self) -> dict:
        """获取反馈统计

        Returns:
            {"total": 总数, "by_category": {原始分类: 被修正次数}}
        """
        records = self._read_all()
        by_category: dict[str, int] = {}
        for r in records:
            orig = r.get("original_category", "") or "未知"
            by_category[orig] = by_category.get(orig, 0) + 1
        return {"total": len(records), "by_category": by_category}

    def get_recent_feedbacks(self, limit: int = 100) -> list[dict]:
        """获取最近的反馈记录

        Args:
            limit: 返回条数上限，默认 100

        Returns:
            按时间倒序的反馈记录列表
        """
        records = self._read_all()
        return records[-limit:][::-1]

    def _read_all(self) -> list[dict]:
        """读取全部反馈记录"""
        if not self.feedback_file.exists():
            return []
        records: list[dict] = []
        try:
            with open(self.feedback_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"读取反馈记录失败: {e}")
        return records
