"""高保真原型示例数据 - 严格对齐 email_desktop_ui_design.html 主界面 (浅色模式)

提供与设计稿一致的 9 封示例邮件、文件夹未读数、首个邮件的完整正文与附件。
当应用未连接真实邮箱或无已有邮件时，加载本模块数据以呈现高保真原型效果。
"""

from datetime import datetime, timedelta
from typing import Optional

from src.core.models import Attachment, MailData


def _ts(days_ago: int, hour: int, minute: int = 0) -> datetime:
    """生成相对当前时间的发送时间"""
    now = datetime.now()
    dt = now - timedelta(days=days_ago)
    return dt.replace(hour=hour, minute=minute, second=0, microsecond=0)


# 首封邮件正文（Markdown，对齐设计稿 .email-body 结构）
FIRST_MAIL_BODY = """Hi 各位同事，

大家好！附件是 Q3 季度产品路线图的正式版文档，本次评审会议安排如下：

#### 会议信息

- **时间**：2024 年 8 月 8 日（周四）下午 14:00 - 16:00
- **地点**：总部大楼 3F - 星辰会议室
- **线上**：https://meeting.company.com/room/888

#### 评审议程

- Q2 产品目标完成情况回顾（30 min）
- Q3 核心产品路线图讲解（40 min）
- 各模块负责人反馈与讨论（40 min）
- 优先级确认与资源对齐（10 min）

请大家**务必在周三之前**阅读完附件中的文档，并在评论区留下您的意见和建议。如果有任何疑问，欢迎随时回复邮件或直接联系我。

期待大家的精彩反馈！
Best regards,
产品设计团队 · 王明
"""


def build_demo_mails() -> list[MailData]:
    """构建与设计稿一致的 9 封示例邮件"""
    now = datetime.now()
    receive = now

    mails: list[MailData] = []

    # 1. 产品设计团队（未读 + 选中 + 星标，带 2 附件）
    mails.append(MailData(
        message_id="demo-001",
        sender="产品设计团队 <product-design@company.com>",
        sender_domain="company.com",
        recipient="我",
        subject="Q3 产品路线图评审 - 请查收附件并反馈",
        send_time=_ts(0, 9, 32),
        receive_time=receive,
        body_text=FIRST_MAIL_BODY,
        body_html=None,
        attachments=[
            Attachment(filename="Q3_产品路线图_v2.0.pdf", size=3_200_000, mime_type="application/pdf"),
            Attachment(filename="Q2_数据复盘.xlsx", size=1_600_000, mime_type="application/vnd.ms-excel"),
        ],
        is_read=False,
        tags=["工作", "项目 Alpha"],
        priority="high",
        category="工作",
        status="new",
    ))

    # 2. 张晓明 (HR)（未读，重要）
    mails.append(MailData(
        message_id="demo-002",
        sender="张晓明 (HR) <zhangxiaoming@company.com>",
        sender_domain="company.com",
        recipient="我",
        subject="【重要】年度绩效考核提交截止提醒",
        send_time=_ts(0, 9, 15),
        receive_time=receive,
        body_text="Dear All, 年度绩效考核系统将于本周五 18:00 关闭，请大家尽快完成自评与反馈提交...",
        body_html=None,
        is_read=False,
        tags=["重要"],
        priority="high",
        category="审批",
        status="new",
    ))

    # 3. 李雨桐（已读 + 星标）
    mails.append(MailData(
        message_id="demo-003",
        sender="李雨桐 <liyutong@company.com>",
        sender_domain="company.com",
        recipient="我",
        subject="Re: 设计规范文档 v2.0 修订意见",
        send_time=_ts(1, 16, 40),
        receive_time=receive,
        body_text="Hi，我看过新版本的设计规范了，整体非常清晰！有几处小建议...",
        body_html=None,
        is_read=True,
        tags=["财务"],
        priority="normal",
        category="资讯",
        status="processed",
    ))

    # 4. GitHub（未读）
    mails.append(MailData(
        message_id="demo-004",
        sender="GitHub <noreply@github.com>",
        sender_domain="github.com",
        recipient="我",
        subject="[flet-email-app] Pull request #42 merged",
        send_time=_ts(1, 10, 22),
        receive_time=receive,
        body_text='The pull request "Feature: Add dark mode support" has been successfully merged...',
        body_html=None,
        is_read=False,
        tags=[],
        priority="normal",
        category="资讯",
        status="new",
    ))

    # 5. 王总（已读，会议）
    mails.append(MailData(
        message_id="demo-005",
        sender="王总 <wangboss@company.com>",
        sender_domain="company.com",
        recipient="我",
        subject="下周一团队会议时间调整 - 请确认出席",
        send_time=_ts(6, 11, 0),
        receive_time=receive,
        body_text="各位同事好，因日程冲突，下周一的团队例会时间从 10:00 调整至 14:00，请确认出席...",
        body_html=None,
        is_read=True,
        tags=["会议"],
        priority="normal",
        category="审批",
        status="processed",
    ))

    # 6. 支付宝（已读 + 星标）
    mails.append(MailData(
        message_id="demo-006",
        sender="支付宝 <service@alipay.com>",
        sender_domain="alipay.com",
        recipient="我",
        subject="您的月度账单已生成，请查收",
        send_time=_ts(5, 8, 30),
        receive_time=receive,
        body_text="尊敬的用户，您 2024 年 7 月的账单已生成，本月消费总计 ¥2,856.50...",
        body_html=None,
        is_read=True,
        tags=[],
        priority="normal",
        category="资讯",
        status="processed",
    ))

    # 7. Figma（已读）
    mails.append(MailData(
        message_id="demo-007",
        sender="Figma <noreply@figma.com>",
        sender_domain="figma.com",
        recipient="我",
        subject="Weekly design inspiration #128",
        send_time=_ts(12, 9, 0),
        receive_time=receive,
        body_text="This week: top mobile UI patterns, 10 new Figma plugins, and an interview with...",
        body_html=None,
        is_read=True,
        tags=[],
        priority="normal",
        category="资讯",
        status="processed",
    ))

    # 8. 妈妈（已读，个人）
    mails.append(MailData(
        message_id="demo-008",
        sender="妈妈 <mom@family.com>",
        sender_domain="family.com",
        recipient="我",
        subject="周末回家吃饭吗？",
        send_time=_ts(13, 19, 15),
        receive_time=receive,
        body_text="儿子，这周周末忙不忙啊？回家吃饭吗？你爸说想跟你喝点儿...",
        body_html=None,
        is_read=True,
        tags=["个人"],
        priority="normal",
        category="资讯",
        status="processed",
    ))

    # 9. LinkedIn（已读）
    mails.append(MailData(
        message_id="demo-009",
        sender="LinkedIn <noreply@linkedin.com>",
        sender_domain="linkedin.com",
        recipient="我",
        subject="5 个人查看了你的档案 - 本周新机会",
        send_time=_ts(14, 7, 45),
        receive_time=receive,
        body_text="本周有 5 位招聘人员查看了您的档案，其中包括字节跳动、腾讯等公司...",
        body_html=None,
        is_read=True,
        tags=[],
        priority="normal",
        category="资讯",
        status="processed",
    ))

    return mails


# 文件夹未读数（对齐设计稿徽章）
DEMO_FOLDER_COUNTS: dict[str, int] = {
    "inbox": 12,
    "drafts": 3,
    "starred": 8,
    "attachments": 25,
}


def first_mail() -> Optional[MailData]:
    """获取首封邮件（用于默认选中并展示详情）"""
    mails = build_demo_mails()
    return mails[0] if mails else None
