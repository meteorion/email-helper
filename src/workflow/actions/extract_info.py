"""AI 提取关键字段 Action：调用 LLMClient.chat 从邮件正文提取结构化字段。"""

from __future__ import annotations

import json
import re
from typing import Any

from src.workflow.actions.base import BaseAction


class ExtractInfoAction(BaseAction):
    """AI 提取邮件关键字段，返回字段字典。"""

    action_name = "extract_info"

    def execute(self) -> Any:
        fields = self.config.get("fields", []) or []
        use_ai = self.config.get("use_ai", True)
        if not use_ai:
            # 非智能模式：返回空字段占位
            return {f: "" for f in fields} if isinstance(fields, list) else {}

        llm = self._require_dep("llm_client")
        mail = self._mail()

        fields_desc = "、".join(fields) if isinstance(fields, list) else str(fields)
        system_prompt = (
            "你是一个信息提取助手。请从邮件中提取以下字段: "
            f"{fields_desc}。严格按 JSON 对象返回，键为字段名，值为提取结果。"
            "无法提取的字段返回空字符串。不要输出 JSON 以外的内容。"
        )
        user_prompt = (
            f"发件人: {getattr(mail, 'sender', '')}\n"
            f"主题: {getattr(mail, 'subject', '')}\n"
            f"正文:\n{getattr(mail, 'body_text', '')[:1000]}\n"
        )

        response = self._call_llm(llm, system_prompt, user_prompt)
        return self._parse_response(response, fields)

    @staticmethod
    def _call_llm(llm, system_prompt: str, user_prompt: str) -> str:
        """兼容 chat_completion / chat 两种接口。"""
        if hasattr(llm, "chat_completion"):
            return llm.chat_completion(system_prompt, user_prompt) or ""
        if hasattr(llm, "chat"):
            return llm.chat(system_prompt, user_prompt) or ""
        raise RuntimeError("LLMClient 缺少 chat_completion/chat 方法")

    def _parse_response(self, response: str, fields) -> dict:
        """从 LLM 响应中解析 JSON 字段字典。"""
        if not response:
            return {f: "" for f in fields} if isinstance(fields, list) else {}
        # 直接解析
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        # 提取第一个 JSON 对象
        match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        # 兜底：返回空字段
        self.logger.warning(f"LLM 响应无法解析为 JSON: {response[:200]}")
        if isinstance(fields, list):
            return {f: "" for f in fields}
        return {}
