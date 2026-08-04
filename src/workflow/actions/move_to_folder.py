"""移动邮件夹 Action（stub）。

企微 IMAP 不一定支持 MOVE 命令，Alpha 阶段仅做尝试性调用与日志记录，
若 imap_client 不提供 move_to_folder 方法则跳过实际操作。
"""

from __future__ import annotations

from typing import Any

from src.workflow.actions.base import BaseAction


class MoveToFolderAction(BaseAction):
    """移动邮件到指定文件夹（企微 IMAP 兼容性存疑，降级为日志记录）。"""

    action_name = "move_to_folder"

    def execute(self) -> Any:
        folder = self.config.get("folder_name", "")
        if not folder:
            raise ValueError("move_to_folder 缺少 folder_name")

        imap = self._dep("imap_client")
        mail = self._mail()

        if imap is None:
            self.logger.warning(
                f"move_to_folder: imap_client 未注入，仅记录目标文件夹 {folder}"
            )
            return {"status": "skipped", "folder": folder, "reason": "imap_client 未注入"}

        move_fn = getattr(imap, "move_to_folder", None)
        if move_fn is None:
            self.logger.warning(
                "move_to_folder: 企微 IMAP 不一定支持 MOVE 命令，跳过实际操作"
            )
            return {
                "status": "skipped",
                "folder": folder,
                "reason": "imap_client 不支持 move_to_folder",
            }

        try:
            move_fn(mail.message_id, folder)
            return {"status": "moved", "folder": folder}
        except Exception as exc:
            self.logger.warning(
                f"move_to_folder: IMAP MOVE 失败 (可能不支持): {exc}"
            )
            return {
                "status": "skipped",
                "folder": folder,
                "reason": f"IMAP MOVE 失败: {exc}",
            }
