"""Prompt 构建器模块

根据 design.md 4.2.3 构建分类 / 信息提取 / 摘要三种 Prompt。
"""

from src.core.models import MailData


# 分类体系 8 大类
CATEGORIES: list[str] = [
    "审批类",
    "通知类",
    "会议类",
    "协作类",
    "资讯类",
    "告警类",
    "营销类",
    "垃圾邮件",
]

# 优先级
PRIORITIES: list[str] = ["紧急", "普通", "低优先级"]


class PromptBuilder:
    """Prompt 构建器，生成 system / user 提示词"""

    # 分类系统提示词，严格对齐 design.md 4.2.3
    SYSTEM_PROMPT: str = """你是一个专业的邮件分类助手，专注于企业微信邮件场景。

## 分类体系
请根据邮件内容判断属于以下类别之一:
- 审批类: 需要审批流程、签字确认、权限申请等
- 通知类: 公告、政策变更、系统通知等仅需知晓的信息
- 会议类: 会议邀请、日程安排、时间协调
- 协作类: 工作沟通、问题讨论、需要回复的邮件
- 资讯类: 内部通讯、周报月报、行业资讯、订阅内容
- 告警类: 系统告警、监控通知、异常报告
- 营销类: 产品推广、广告、活动邀请
- 垃圾邮件: 无关、诈骗、恶意内容

## 判断维度
1. 紧急程度: [紧急, 普通, 低优先级]
   - 紧急: 包含截止时间<24h、"紧急"、"ASAP"等关键词
   - 普通: 常规工作邮件
   - 低优先级: 资讯、营销、可延后处理

2. 是否需要回复: [是, 否]
   - 是: 需要明确回复、提供反馈、确认收到
   - 否: 仅通知、公告、自动发送

3. 置信度: [0.0-1.0]
   - 0.9-1.0: 非常确定，特征明显
   - 0.7-0.9: 较确定，有一定模糊性
   - 0.5-0.7: 不确定，需要人工确认
   - <0.5: 非常不确定，建议人工处理

## 输出格式
严格按以下JSON格式返回，不要包含其他内容:
{
  "category": "分类名称",
  "priority": "紧急/普通/低优先级",
  "need_reply": true/false,
  "confidence": 0.85,
  "reason": "分类理由(50字内)"
}

## 示例
示例1:
发件人: hr@company.com
主题: Q3预算审批申请
正文: 请审批附件中的Q3部门预算...
输出: {"category":"审批类","priority":"普通","need_reply":true,"confidence":0.95,"reason":"包含审批关键词和附件"}

示例2:
发件人: system@monitor.com
主题: [ALERT] CPU使用率超过90%
正文: 服务器192.168.1.100 CPU使用率持续超过90%...
输出: {"category":"告警类","priority":"紧急","need_reply":false,"confidence":0.98,"reason":"系统告警，包含ALERT标记"}"""

    def build_classify_prompt(self, mail: MailData) -> tuple[str, str]:
        """构建分类 Prompt

        Args:
            mail: 邮件数据

        Returns:
            (system_prompt, user_prompt) 元组。
            system: 8 大分类 + 优先级 + need_reply + 严格 JSON 输出格式
            user: 邮件主题 + 发件人 + 正文摘要（前 500 字）
        """
        body_summary = (mail.body_text or "")[:500]
        attachments = ", ".join(
            a.filename for a in mail.attachments if a.filename
        ) or "无"
        send_time = mail.send_time.isoformat() if mail.send_time else ""

        user_prompt = (
            f"发件人: {mail.sender}\n"
            f"发件人域名: {mail.sender_domain}\n"
            f"主题: {mail.subject}\n"
            f"正文摘要(前500字): {body_summary}\n"
            f"附件列表: {attachments}\n"
            f"发送时间: {send_time}"
        )
        return self.SYSTEM_PROMPT, user_prompt

    def build_extract_prompt(
        self, mail: MailData, fields: list[str]
    ) -> tuple[str, str]:
        """构建关键信息提取 Prompt

        Args:
            mail: 邮件数据
            fields: 需要提取的字段名列表

        Returns:
            (system_prompt, user_prompt) 元组
        """
        fields_str = ", ".join(fields)
        system_prompt = (
            "你是一个专业的邮件信息提取助手。请从邮件中提取指定字段，"
            "严格按 JSON 格式返回，key 为字段名，value 为提取到的值，"
            "找不到的字段返回空字符串。不要输出 JSON 以外的内容。\n"
            f"需要提取的字段: {fields_str}"
        )
        body_summary = (mail.body_text or "")[:500]
        user_prompt = (
            f"发件人: {mail.sender}\n"
            f"主题: {mail.subject}\n"
            f"正文摘要: {body_summary}"
        )
        return system_prompt, user_prompt

    def build_summary_prompt(
        self, mail: MailData, max_length: int = 200
    ) -> tuple[str, str]:
        """构建摘要生成 Prompt

        Args:
            mail: 邮件数据
            max_length: 摘要最大字数，默认 200

        Returns:
            (system_prompt, user_prompt) 元组
        """
        system_prompt = (
            "你是一个邮件摘要助手。请用简洁的语言概括邮件核心内容，"
            f"不超过 {max_length} 字，直接输出摘要文本，不要包含其他说明。"
        )
        user_prompt = (
            f"发件人: {mail.sender}\n"
            f"主题: {mail.subject}\n"
            f"正文: {mail.body_text or ''}"
        )
        return system_prompt, user_prompt
