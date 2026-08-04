"""邮件详情组件 - Flet 实现

简洁清新风格：无图标、无 emoji，圆角化操作按钮，附件用文字卡片。
配色遵循 theme.Color 规范，支持深浅主题。
"""

import flet as ft

from src.core.models import MailData
from src.core.logger import get_logger
from src.gui.theme import Color, DarkColor, Radius, Font

logger = get_logger("gui.mail_detail")


@ft.control("Column", init=False)
class MailDetailView(ft.Column):
    """邮件详情视图"""

    def __init__(self, is_dark: bool = False):
        super().__init__()
        self.spacing = 0
        self.expand = True
        self._current_mail = None
        self._is_dark = is_dark

        # 空状态（文字提示，无图标）
        self._empty_view = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "邮件",
                        size=32,
                        weight=ft.FontWeight.W_300,
                        color=self._colors.TEXT_PLACEHOLDER,
                    ),
                    ft.Text(
                        "选择一封邮件查看详情",
                        size=Font.BODY,
                        color=self._colors.TEXT_SECONDARY,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            expand=True,
            alignment="center",
        )

        # 详情内容容器
        self._detail_view = ft.Column(spacing=0, expand=True, visible=False, scroll=ft.ScrollMode.AUTO)

        # 头部字段
        self._sender_text = ft.Text(size=15, weight=ft.FontWeight.W_600)
        self._email_text = ft.Text(size=Font.BODY, color=self._colors.TEXT_SECONDARY)
        self._time_text = ft.Text(size=Font.AUX, color=self._colors.TEXT_SECONDARY)
        self._subject_text = ft.Text(size=Font.WINDOW_TITLE, weight=ft.FontWeight.W_700)

        # 正文
        self._body_md = ft.Markdown(
            "",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            soft_line_break=True,
        )

        # 附件区
        self._attachments_col = ft.Column(spacing=8, visible=False)

        # 操作按钮（文字按钮，圆角）
        self._action_bar = self._build_action_bar()

        # 组装详情视图
        self._detail_view.controls = [
            self._build_header(),
            self._build_body(),
            self._build_attachments_section(),
            self._action_bar,
        ]

        self.controls = [self._empty_view, self._detail_view]

    # ---- 颜色辅助 ----
    @property
    def _colors(self):
        return DarkColor if self._is_dark else Color

    # ---- 区块构建 ----
    def _build_header(self) -> ft.Container:
        c = self._colors
        return ft.Container(
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
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.Container(height=6),
                    self._subject_text,
                ],
                spacing=4,
            ),
            padding=ft.Padding(left=24, top=24, right=24, bottom=16),
            border=ft.Border.only(bottom=ft.border.BorderSide(1, c.BORDER)),
        )

    def _build_body(self) -> ft.Container:
        c = self._colors
        return ft.Container(
            content=self._body_md,
            padding=ft.Padding(left=24, top=20, right=24, bottom=16),
            expand=True,
            bgcolor=c.BG_CARD,
        )

    def _build_attachments_section(self) -> ft.Container:
        c = self._colors
        return ft.Container(
            content=self._attachments_col,
            padding=ft.Padding(left=24, right=24, bottom=12),
            border=ft.Border.only(top=ft.border.BorderSide(1, c.BORDER_LIGHT)),
            visible=False,
        )

    def _build_action_bar(self) -> ft.Container:
        c = self._colors
        # 文字按钮，圆角，无图标
        reply_btn = self._make_action_btn("回复", c.PRIMARY, on_click=self._on_reply)
        forward_btn = self._make_action_btn("转发", c.PRIMARY, on_click=self._on_forward)
        mark_btn = self._make_action_btn("标记已读", c.TEXT_SECONDARY, on_click=self._on_mark_read)
        delete_btn = self._make_action_btn("删除", c.ERROR, on_click=self._on_delete)

        return ft.Container(
            content=ft.Row(
                [
                    reply_btn,
                    forward_btn,
                    mark_btn,
                    ft.Container(expand=True),
                    delete_btn,
                ],
                spacing=12,
            ),
            padding=ft.Padding(left=20, right=20, top=10, bottom=16),
            border=ft.Border.only(top=ft.border.BorderSide(1, c.BORDER)),
        )

    def _make_action_btn(self, text: str, color: str, on_click=None) -> ft.Container:
        """制作圆角文字按钮"""
        c = self._colors
        return ft.Container(
            content=ft.Text(
                text,
                size=Font.BODY,
                color=color,
                weight=ft.FontWeight.W_500,
            ),
            on_click=on_click,
            padding=ft.Padding(left=14, top=7, right=14, bottom=7),
            border_radius=Radius.BUTTON,
            ink=True,
            bgcolor=c.BG_HOVER,
        )

    # ---- 显示邮件 ----
    def show_mail(self, mail: MailData):
        """显示邮件详情"""
        self._current_mail = mail

        self._empty_view.visible = False
        self._detail_view.visible = True

        # 发件人拆分
        name = mail.sender
        email = ""
        if "<" in mail.sender and ">" in mail.sender:
            name = mail.sender.split("<")[0].strip()
            email = mail.sender.split("<")[1].split(">")[0]

        c = self._colors
        self._sender_text.value = name
        self._sender_text.color = c.TEXT_PRIMARY
        self._email_text.value = f"<{email}>" if email else ""
        self._email_text.color = c.TEXT_SECONDARY
        self._time_text.value = mail.send_time.strftime("%Y-%m-%d %H:%M:%S")
        self._time_text.color = c.TEXT_SECONDARY
        self._subject_text.value = mail.subject
        self._subject_text.color = c.TEXT_PRIMARY

        # 正文
        self._body_md.value = mail.body_html if mail.body_html else mail.body_text

        # 附件
        self._attachments_col.controls.clear()
        attachments_section = self._detail_view.controls[2]
        if mail.attachments:
            attachments_section.visible = True
            self._attachments_col.visible = True
            # 附件标题（文字，无 emoji）
            self._attachments_col.controls.append(
                ft.Text(
                    f"{len(mail.attachments)} 个附件",
                    size=Font.PANEL_TITLE,
                    weight=ft.FontWeight.W_600,
                    color=c.TEXT_PRIMARY,
                )
            )
            for att in mail.attachments:
                size_mb = att.size / (1024 * 1024)
                size_text = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{att.size / 1024:.1f} KB"
                self._attachments_col.controls.append(self._build_attachment_card(att, size_text))
        else:
            attachments_section.visible = False
            self._attachments_col.visible = False

        logger.info(f"显示邮件详情: {mail.subject}")
        self.update()

    def _build_attachment_card(self, att, size_text: str) -> ft.Container:
        """构建附件卡片（文件名 + 大小，无图标）"""
        c = self._colors
        # 扩展名标签
        ext = ""
        if "." in att.filename:
            ext = att.filename.rsplit(".", 1)[-1].upper()[:4]

        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Text(
                            ext or "FILE",
                            size=Font.SMALL,
                            color=c.PRIMARY,
                            weight=ft.FontWeight.W_700,
                        ),
                        width=44,
                        height=44,
                        alignment="center",
                        bgcolor=c.PRIMARY_CONTAINER,
                        border_radius=Radius.CARD,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                att.filename,
                                size=Font.BODY,
                                color=c.TEXT_PRIMARY,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                size_text,
                                size=Font.AUX,
                                color=c.TEXT_SECONDARY,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=12, top=10, right=12, bottom=10),
            border_radius=Radius.CARD,
            bgcolor=c.BG_HOVER,
            ink=True,
        )

    # ---- 操作回调（占位，由上层覆盖） ----
    def _on_reply(self, e):
        logger.info("点击回复")

    def _on_forward(self, e):
        logger.info("点击转发")

    def _on_mark_read(self, e):
        logger.info("点击标记已读")

    def _on_delete(self, e):
        logger.info("点击删除")

    # ---- 公共方法 ----
    def clear(self):
        """清空详情"""
        self._current_mail = None
        self._detail_view.visible = False
        self._empty_view.visible = True
        self.update()

    def update_theme(self, is_dark: bool):
        """切换主题时刷新配色"""
        self._is_dark = is_dark
        # 重建空状态文字配色
        self._empty_view.content.controls[0].color = self._colors.TEXT_PLACEHOLDER
        self._empty_view.content.controls[1].color = self._colors.TEXT_SECONDARY
        # 重建详情视图
        self._detail_view.controls = [
            self._build_header(),
            self._build_body(),
            self._build_attachments_section(),
            self._action_bar,
        ]
        # 如有当前邮件，重新填充
        if self._current_mail:
            self.show_mail(self._current_mail)
        else:
            self.update()
