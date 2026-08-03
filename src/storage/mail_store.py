"""邮件存储 - JSON 文件存储"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.core.logger import get_logger
from src.core.models import MailData

logger = get_logger("storage.mail")


class MailStore:
    """邮件 JSON 文件存储"""

    def __init__(self, base_dir: str | Path = "./data"):
        self.base_dir = Path(base_dir)
        self.mails_dir = self.base_dir / "mails"
        self.attachments_dir = self.base_dir / "attachments"
        self.cache_dir = self.base_dir / "cache"
        self.seen_ids_file = self.cache_dir / "seen_ids.json"

        # 确保目录存在
        self.mails_dir.mkdir(parents=True, exist_ok=True)
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def save(self, mail: MailData) -> str:
        """
        保存邮件为 JSON 文件

        Returns:
            保存的文件路径
        """
        try:
            # 按日期组织目录
            date_str = mail.send_time.strftime("%Y-%m-%d")
            date_dir = self.mails_dir / date_str
            date_dir.mkdir(parents=True, exist_ok=True)

            # 生成文件名 (使用 message_id 的 hash)
            mail_hash = hashlib.md5(mail.message_id.encode()).hexdigest()[:8]
            filename = f"mail_{mail_hash}.json"
            file_path = date_dir / filename

            # 保存 JSON
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(mail.to_json())

            # 更新 local_file_path
            mail.local_file_path = str(file_path)

            logger.info(f"保存邮件: {mail.message_id} -> {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"保存邮件失败: {e}", exc_info=True)
            raise

    def load(self, message_id: str) -> Optional[MailData]:
        """
        加载邮件

        Args:
            message_id: 邮件 Message-ID

        Returns:
            MailData 或 None
        """
        try:
            mail_hash = hashlib.md5(message_id.encode()).hexdigest()[:8]
            filename = f"mail_{mail_hash}.json"

            # 在所有日期目录中搜索
            for date_dir in self.mails_dir.iterdir():
                if not date_dir.is_dir():
                    continue
                file_path = date_dir / filename
                if file_path.exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        return MailData.from_json(f.read())

            return None

        except Exception as e:
            logger.error(f"加载邮件失败: {message_id}, 错误: {e}")
            return None

    def list_mails(self, date: Optional[str] = None) -> list[MailData]:
        """
        列出邮件

        Args:
            date: 日期字符串 (YYYY-MM-DD)，None 表示所有日期

        Returns:
            MailData 列表
        """
        mails = []

        try:
            if date:
                # 指定日期
                date_dir = self.mails_dir / date
                if date_dir.exists():
                    mails.extend(self._load_mails_from_dir(date_dir))
            else:
                # 所有日期
                for date_dir in self.mails_dir.iterdir():
                    if date_dir.is_dir():
                        mails.extend(self._load_mails_from_dir(date_dir))

            # 按发送时间倒序
            mails.sort(key=lambda m: m.send_time, reverse=True)
            return mails

        except Exception as e:
            logger.error(f"列出邮件失败: {e}")
            return mails

    def _load_mails_from_dir(self, date_dir: Path) -> list[MailData]:
        """从目录加载所有邮件"""
        mails = []
        for file_path in date_dir.glob("mail_*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    mail = MailData.from_json(f.read())
                    mails.append(mail)
            except Exception as e:
                logger.warning(f"加载邮件文件失败: {file_path}, 错误: {e}")
        return mails

    def get_seen_ids(self) -> set[str]:
        """获取已处理邮件 ID 集合"""
        try:
            if not self.seen_ids_file.exists():
                return set()

            with open(self.seen_ids_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("seen_ids", []))

        except Exception as e:
            logger.error(f"加载 seen_ids 失败: {e}")
            return set()

    def save_seen_ids(self, seen_ids: set[str]):
        """保存已处理邮件 ID"""
        try:
            data = {
                "updated_at": datetime.now().isoformat(),
                "count": len(seen_ids),
                "seen_ids": list(seen_ids),
            }

            with open(self.seen_ids_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"保存 seen_ids: {len(seen_ids)} 条记录")

        except Exception as e:
            logger.error(f"保存 seen_ids 失败: {e}")
            raise

    def update_mail(self, mail: MailData) -> bool:
        """
        更新邮件 (例如标记已读)

        Returns:
            是否成功
        """
        if not mail.local_file_path:
            logger.warning(f"邮件没有本地路径，无法更新: {mail.message_id}")
            return False

        try:
            file_path = Path(mail.local_file_path)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(mail.to_json())
            logger.info(f"更新邮件: {mail.message_id}")
            return True

        except Exception as e:
            logger.error(f"更新邮件失败: {e}")
            return False
