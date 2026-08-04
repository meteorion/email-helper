"""保存附件 Action：把邮件附件复制到指定目录。"""

from __future__ import annotations

import os
import shutil
from typing import Any

from src.workflow.actions.base import BaseAction


class SaveAttachmentAction(BaseAction):
    """把邮件附件复制到指定目录，返回保存路径列表。"""

    action_name = "save_attachment"

    def execute(self) -> Any:
        mail = self._mail()
        target_dir = self.config.get("path", "./data/attachments/")
        filename_pattern = self.config.get("filename_pattern", "{filename}")

        os.makedirs(target_dir, exist_ok=True)
        saved_paths: list[str] = []

        for att in getattr(mail, "attachments", []) or []:
            local_path = getattr(att, "local_path", None)
            if not local_path or not os.path.exists(local_path):
                self.logger.warning(f"附件本地文件不存在，跳过: {getattr(att, 'filename', '')}")
                continue

            filename = self._build_filename(filename_pattern, att, mail)
            target_path = os.path.join(target_dir, filename)
            target_path = self._avoid_overwrite(target_path)

            try:
                shutil.copy2(local_path, target_path)
                saved_paths.append(target_path)
                self.logger.info(f"附件已保存: {target_path}")
            except OSError as exc:
                self.logger.error(f"附件保存失败 {local_path} -> {target_path}: {exc}")

        return {"saved_paths": saved_paths, "count": len(saved_paths)}

    def _build_filename(self, pattern: str, att, mail) -> str:
        """按 pattern 渲染文件名并做安全过滤。"""
        try:
            filename = pattern.format(
                filename=getattr(att, "filename", "attachment"),
                sender=getattr(mail, "sender", ""),
                date=str(getattr(mail, "send_time", "")),
            )
        except (KeyError, IndexError):
            filename = getattr(att, "filename", "attachment")
        # 仅保留安全字符
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        return safe or "attachment"

    @staticmethod
    def _avoid_overwrite(path: str) -> str:
        """同名文件追加序号避免覆盖。"""
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        counter = 1
        while os.path.exists(f"{base}_{counter}{ext}"):
            counter += 1
        return f"{base}_{counter}{ext}"
