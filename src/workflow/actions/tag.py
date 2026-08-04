"""打标签 Action：调用 MailRepository.update_tags 更新邮件标签。"""

from __future__ import annotations

from typing import Any

from src.workflow.actions.base import BaseAction


class TagAction(BaseAction):
    """为邮件打标签，支持 add/replace/remove 三种模式。"""

    action_name = "tag"

    def execute(self) -> Any:
        repo = self._require_dep("mail_repository")
        mail = self._mail()
        tags = self.config.get("tags", []) or []
        if isinstance(tags, str):
            tags = [tags]
        mode = self.config.get("mode", "add")  # add / replace / remove

        existing = list(getattr(mail, "tags", []) or [])

        if mode == "replace":
            new_tags = list(tags)
        elif mode == "remove":
            new_tags = [t for t in existing if t not in tags]
        else:  # add
            new_tags = list(existing)
            for t in tags:
                if t not in new_tags:
                    new_tags.append(t)

        repo.update_tags(mail.message_id, new_tags)
        # 同步更新内存中 mail 对象的 tags
        try:
            mail.tags = new_tags
        except Exception:
            pass
        return {"tags": new_tags, "mode": mode}
