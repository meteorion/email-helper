"""AI 生成摘要 Action：调用 LLMClient 生成邮件摘要。"""

from __future__ import annotations

from typing import Any

from src.workflow.actions.base import BaseAction


class SummarizeAction(BaseAction):
    """AI 生成邮件摘要，返回摘要文本。"""

    action_name = "summarize"

    def execute(self) -> Any:
        llm = self._require_dep("llm_client")
        max_length = self.config.get("max_length", 200)
        mail = self._mail()

        system_prompt = (
            f"你是一个邮件摘要助手。请生成不超过 {max_length} 字的邮件摘要，"
            "突出关键信息（主题、发件人意图、关键时间/金额/待办等）。"
        )
        user_prompt = (
            f"主题: {getattr(mail, 'subject', '')}\n"
            f"发件人: {getattr(mail, 'sender', '')}\n"
            f"正文:\n{getattr(mail, 'body_text', '')[:2000]}\n"
        )

        if hasattr(llm, "chat_completion"):
            response = llm.chat_completion(system_prompt, user_prompt) or ""
        elif hasattr(llm, "chat"):
            response = llm.chat(system_prompt, user_prompt) or ""
        else:
            raise RuntimeError("LLMClient 缺少 chat_completion/chat 方法")

        # 截断到 max_length
        if max_length and isinstance(max_length, int) and len(response) > max_length:
            response = response[:max_length]
        return response
