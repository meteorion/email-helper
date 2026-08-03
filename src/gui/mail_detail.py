"""邮件详情组件 - Flet 实现"""

import flet as ft
from src.core.models import MailData
from src.core.logger import get_logger

logger = get_logger("gui.mail_detail")


class MailDetailView(ft.Column):
    """邮件详情视图"""

    def __init__(self):
        super().__init__()
        self.spacing = 0
        self.expand = True
        self._current_mail = None

        # 空状态
        self._empty_view = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.EMAIL_OUTLINED, size=64, color=ft.Colors.GREY_300),
                    ft.Text("选择一封邮件查看详情", size=14, color=ft.Colors.GREY_400),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            expand=True,
            alignment=ft.Alignment(0, 0),
        )

        # 详情内容
        self._detail_view = ft.Column(spacing=0, expand=True, visible=False)

        # 头部
        self._sender_text = ft.Text(size=16, weight=ft.FontWeight.W_600)
        self._email_text = ft.Text(size=13, color=ft.Colors.GREY_500)
        self._time_text = ft.Text(size=13, color=ft.Colors.GREY_500)
        self._subject_text = ft.Text(size=18, weight=ft.FontWeight.W_700)

        self._detail_view.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                self._sender_text,
                                self._email_text,
                                ft.Container(expand=True),
                                self._time_text,
                            ],
                            spacing=8,
                        ),
                        ft.Container(height=8),
                        self._subject_text,
                    ],
                    spacing=4,
                ),
                padding=24,
                border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.GREY_200)),
            )
        )

        # 正文
        self._body_md = ft.Markdown(
            "",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            
        )
        self._detail_view.controls.append(
            ft.Container(
                content=self._body_md,
                padding=24,
                expand=True,
            )
        )

        # 附件区域
        self._attachments_col = ft.Column(spacing=8, visible=False)
        self._detail_view.controls.append(
            ft.Container(
                content=self._attachments_col,
                padding=ft.Padding(left=24, right=24, bottom=12),
            )
        )

        # 操作按钮
        self._detail_view.controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.TextButton("回复", icon=ft.Icons.REPLY),
                        ft.TextButton("转发", icon=ft.Icons.FORWARD),
                        ft.TextButton("标记已读", icon=ft.Icons.MARK_EMAIL_READ),
                        ft.Container(expand=True),
                        ft.TextButton("删除", icon=ft.Icons.DELETE_OUTLINE),
                    ],
                    spacing=8,
                ),
                padding=ft.Padding(left=12, right=12, top=8, bottom=16),
                border=ft.Border(top=ft.BorderSide(1, ft.Colors.GREY_200)),
            )
        )

        self.controls = [self._empty_view, self._detail_view]

    def show_mail(self, mail: MailData):
        """显示邮件详情"""
        self._current_mail = mail

        self._empty_view.visible = False
        self._detail_view.visible = True

        # 发件人
        name = mail.sender
        email = ""
        if "<" in mail.sender and ">" in mail.sender:
            name = mail.sender.split("<")[0].strip()
            email = mail.sender.split("<")[1].split(">")[0]

        self._sender_text.value = name
        self._email_text.value = f"<{email}>" if email else ""
        self._time_text.value = mail.send_time.strftime("%Y-%m-%d %H:%M:%S")
        self._subject_text.value = mail.subject

        # 正文
        if mail.body_html:
            self._body_md.value = mail.body_html
        else:
            self._body_md.value = mail.body_text

        # 附件
        self._attachments_col.controls.clear()
        if mail.attachments:
            self._attachments_col.visible = True
            self._attachments_col.controls.append(
                ft.Text(
                    f"📎 {len(mail.attachments)} 个附件",
                    size=13,
                    weight=ft.FontWeight.W_600,
                )
            )
            for att in mail.attachments:
                size_mb = att.size / (1024 * 1024)
                size_text = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{att.size / 1024:.1f} KB"
                self._attachments_col.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.ATTACH_FILE, size=16, color=ft.Colors.GREY_600),
                                ft.Text(att.filename, size=13),
                                ft.Container(expand=True),
                                ft.Text(size_text, size=12, color=ft.Colors.GREY_500),
                            ],
                            spacing=8,
                        ),
                        padding=ft.Padding(left=12, top=8, right=12, bottom=8),
                        border_radius=8,
                        bgcolor=ft.Colors.GREY_50,
                    )
                )
        else:
            self._attachments_col.visible = False

        logger.info(f"显示邮件详情: {mail.subject}")
        self.update()

    def clear(self):
        """清空详情"""
        self._current_mail = None
        self._detail_view.visible = False
        self._empty_view.visible = True
        self.update()