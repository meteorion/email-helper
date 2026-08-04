"""邮件详情组件 - Flet 实现（第四栏）

严格对齐 email_desktop_ui_design.html 设计稿：
  - 顶部工具栏：圆角按钮（返回/归档/删除/标记未读/移动到/标签）+ 头像组
  - 详情内容（padding 28px 36px）：
      大标题 24px Bold + 标签
      发件人区（48px 圆形渐变头像 + 姓名/邮箱/收件人 + 时间）
      正文 Markdown
      附件卡片（200px 宽 + 预览图 + 文件名 + 大小）
  - 底部回复区：快捷操作 + 工具栏 + 输入框 + 发送按钮
"""

import flet as ft

from src.core.models import MailData
from src.core.logger import get_logger
from src.gui.theme import Color, DarkColor, Radius, Font, TAG_COLOR_MAP

logger = get_logger("gui.mail_detail")


# 附件扩展名 → 预览配置：(渐变色属性, 显示文字)
ATTACH_PRESETS = {
    ".pdf": ("ATTACH_PDF_GRADIENT", "PDF", "rgba(220,38,38,0.9)"),
    ".doc": ("ATTACH_XLS_GRADIENT", "DOC", "rgba(37,99,235,0.9)"),
    ".docx": ("ATTACH_XLS_GRADIENT", "DOC", "rgba(37,99,235,0.9)"),
    ".xls": ("ATTACH_XLS_GRADIENT", "XLS", "rgba(37,99,235,0.9)"),
    ".xlsx": ("ATTACH_XLS_GRADIENT", "XLS", "rgba(37,99,235,0.9)"),
    ".ppt": ("ATTACH_XLS_GRADIENT", "PPT", "rgba(37,99,235,0.9)"),
    ".pptx": ("ATTACH_XLS_GRADIENT", "PPT", "rgba(37,99,235,0.9)"),
    ".zip": ("ATTACH_XLS_GRADIENT", "ZIP", "rgba(37,99,235,0.9)"),
    ".rar": ("ATTACH_XLS_GRADIENT", "ZIP", "rgba(37,99,235,0.9)"),
    ".png": ("ATTACH_XLS_GRADIENT", "IMG", "rgba(37,99,235,0.9)"),
    ".jpg": ("ATTACH_XLS_GRADIENT", "IMG", "rgba(37,99,235,0.9)"),
    ".jpeg": ("ATTACH_XLS_GRADIENT", "IMG", "rgba(37,99,235,0.9)"),
}


def _extract_sender(sender: str) -> tuple[str, str]:
    """从 sender 提取 (显示名, 邮箱)"""
    if "<" in sender and ">" in sender:
        name = sender.split("<")[0].strip().strip('"')
        email = sender.split("<")[1].split(">")[0].strip()
        return (name or email, email)
    return (sender.strip().strip('"'), "")


def _get_avatar_letter(name: str) -> str:
    if not name:
        return "?"
    return name[0].upper()


def _format_size(size: int) -> str:
    """格式化文件大小"""
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    elif size >= 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size} B"


def _format_time(dt) -> str:
    """格式化时间"""
    from datetime import datetime, timedelta
    now = datetime.now()
    if dt.date() == now.date():
        return f"今天 {dt.strftime('%H:%M')}"
    elif dt.date() == (now - timedelta(days=1)).date():
        return f"昨天 {dt.strftime('%H:%M')}"
    else:
        return dt.strftime("%Y-%m-%d %H:%M")


def _get_tag_colors(tag: str, colors):
    attr = "TAG_" + TAG_COLOR_MAP.get(tag, "PROJECT")
    return getattr(colors, attr)


@ft.control("Column", init=False)
class MailDetailView(ft.Column):
    """邮件详情视图"""

    def __init__(self, is_dark: bool = False):
        super().__init__()
        self.spacing = 0
        self.expand = True
        self._current_mail: MailData | None = None
        self._is_dark = is_dark

        self._build()

    @property
    def _colors(self):
        return DarkColor if self._is_dark else Color

    # ---- 构建 UI ----
    def _build(self):
        c = self._colors

        # 空状态
        self._empty_view = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.MAIL_OUTLINE, size=64, color=c.TEXT_PLACEHOLDER),
                    ft.Text(
                        "邮件",
                        size=32,
                        weight=ft.FontWeight.W_300,
                        color=c.TEXT_PLACEHOLDER,
                    ),
                    ft.Text(
                        "选择一封邮件查看详情",
                        size=Font.BODY,
                        color=c.TEXT_SECONDARY,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
            expand=True,
            alignment=ft.Alignment(0, 0),
        )

        # 详情容器（工具栏 + 滚动内容 + 回复区）
        self._toolbar = self._build_toolbar()
        self._content_scroll = ft.Column(
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )
        self._reply_section = self._build_reply_section()

        self._detail_view = ft.Column(
            [self._toolbar, self._content_scroll, self._reply_section],
            spacing=0,
            expand=True,
            visible=False,
        )

        self.controls = [self._empty_view, self._detail_view]

    # ---- 工具栏 ----
    def _build_toolbar(self) -> ft.Container:
        """顶部工具栏（圆角按钮 + 头像组）"""
        c = self._colors

        def make_btn(icon, label, on_click=None):
            return ft.Container(
                content=ft.Row(
                    [ft.Icon(icon, size=14, color=c.TEXT_SECONDARY)] if icon else [],
                    spacing=0,
                ),
                tooltip=label,
                on_click=on_click,
                padding=ft.Padding(8, 5, 8, 5),
                border_radius=15,
                ink=True,
            )

        # 头像组（3 个重叠小头像）
        avatar_gradients = [c.AVATAR_GRADIENT_1, c.AVATAR_GRADIENT_2, c.AVATAR_GRADIENT_3]
        avatar_letters = ["张", "李", "王"]
        mini_avatars = []
        for i, (grad, letter) in enumerate(zip(avatar_gradients, avatar_letters)):
            mini_avatars.append(
                ft.Container(
                    content=ft.Text(
                        letter,
                        size=11,
                        color=c.TEXT_ON_PRIMARY,
                        weight=ft.FontWeight.W_600,
                    ),
                    width=28,
                    height=28,
                    border_radius=50,
                    alignment=ft.Alignment(0, 0),
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(-1, -1),
                        end=ft.Alignment(1, 1),
                        colors=grad,
                    ),
                    border=ft.Border.all(2, c.BG_MAIN),
                    margin=ft.Margin(-6 if i > 0 else 0, 0, 0, 0),
                )
            )

        return ft.Container(
            content=ft.Row(
                [
                    make_btn(ft.Icons.ARROW_BACK, "返回", self._on_back),
                    make_btn(ft.Icons.ARCHIVE_OUTLINED, "归档", self._on_archive),
                    make_btn(ft.Icons.DELETE_OUTLINE, "删除", self._on_delete),
                    # 分隔线
                    ft.Container(
                        width=1,
                        height=20,
                        bgcolor=c.BORDER,
                        margin=ft.Margin(8, 0, 8, 0),
                    ),
                    make_btn(ft.Icons.MARK_EMAIL_UNREAD_OUTLINED, "标记未读", self._on_mark_unread),
                    make_btn(ft.Icons.DRIVE_FILE_MOVE_OUTLINED, "移动到", self._on_move),
                    make_btn(ft.Icons.LABEL_OUTLINED, "标签", self._on_label),
                    make_btn(ft.Icons.MORE_VERT, "更多", self._on_more),
                    ft.Container(expand=True),
                    # 头像组
                    ft.Row(mini_avatars, spacing=0),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(24, 12, 24, 12),
            border=ft.Border(bottom=ft.border.BorderSide(1, c.BORDER_LIGHT)),
        )

    # ---- 详情内容 ----
    def _build_detail_content(self) -> ft.Column:
        """详情内容（大标题 + 标签 + 发件人 + 正文 + 附件）"""
        c = self._colors
        mail = self._current_mail
        assert mail is not None

        sender_name, sender_email = _extract_sender(mail.sender)
        avatar_letter = _get_avatar_letter(sender_name)

        # 大标题
        subject = ft.Text(
            mail.subject or "(无主题)",
            size=Font.DETAIL_SUBJECT,
            weight=ft.FontWeight.W_700,
            color=c.TEXT_PRIMARY,
        )

        # 标签行
        tag_row = ft.Row(spacing=8)
        if mail.tags:
            for tag in mail.tags[:5]:
                bg, txt = _get_tag_colors(tag, c)
                tag_row.controls.append(
                    ft.Container(
                        content=ft.Text(
                            tag,
                            size=Font.TINY,
                            color=txt,
                            weight=ft.FontWeight.W_500,
                        ),
                        bgcolor=bg,
                        border_radius=Radius.TAB,
                        padding=ft.Padding(8, 2, 8, 2),
                    )
                )
        # 优先级标签
        if mail.priority == "high":
            bg, txt = c.TAG_HIGH
            tag_row.controls.append(
                ft.Container(
                    content=ft.Text(
                        "高优先级",
                        size=Font.TINY,
                        color=txt,
                        weight=ft.FontWeight.W_500,
                    ),
                    bgcolor=bg,
                    border_radius=Radius.TAB,
                    padding=ft.Padding(8, 2, 8, 2),
                )
            )

        tags_container = ft.Container(
            content=tag_row,
            margin=ft.Margin(0, 0, 0, 24),
            visible=bool(tag_row.controls),
        )

        # 发件人区
        sender_avatar = ft.Container(
            content=ft.Text(
                avatar_letter,
                size=18,
                color=c.TEXT_ON_PRIMARY,
                weight=ft.FontWeight.W_700,
            ),
            width=48,
            height=48,
            border_radius=50,
            alignment=ft.Alignment(0, 0),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=c.AVATAR_GRADIENT_2,
            ),
        )

        sender_name_text = ft.Text(
            sender_name,
            size=Font.BODY_LG,
            weight=ft.FontWeight.W_600,
            color=c.TEXT_PRIMARY,
        )

        sender_email_text = ft.Text(
            sender_email,
            size=Font.BODY_SM,
            color=c.TEXT_SECONDARY,
        ) if sender_email else ft.Container()

        meta_text = ft.Text(
            f"收件人：{mail.recipient or '我'}",
            size=Font.AUX,
            color=c.TEXT_SECONDARY,
        )

        time_text = ft.Text(
            _format_time(mail.send_time),
            size=Font.BODY_SM,
            color=c.TEXT_SECONDARY,
        )
        attach_count_text = ft.Text(
            f"{len(mail.attachments)} 个附件" if mail.attachments else "",
            size=Font.SMALL,
            color=c.TEXT_SECONDARY,
        ) if mail.attachments else ft.Container()

        sender_section = ft.Container(
            content=ft.Row(
                [
                    sender_avatar,
                    ft.Column(
                        [
                            ft.Row(
                                [sender_name_text, sender_email_text],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            meta_text,
                        ],
                        spacing=4,
                        expand=True,
                    ),
                    ft.Column(
                        [time_text, attach_count_text],
                        spacing=2,
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                    ),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding(0, 16, 0, 16),
            border=ft.Border(
                top=ft.border.BorderSide(1, c.BORDER_LIGHT),
                bottom=ft.border.BorderSide(1, c.BORDER_LIGHT),
            ),
            margin=ft.Margin(0, 0, 0, 28),
        )

        # 正文（Markdown）
        body_content = mail.body_html if mail.body_html else mail.body_text or ""
        body_md = ft.Markdown(
            body_content,
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            soft_line_break=True,
        )
        body_section = ft.Container(
            content=body_md,
            padding=ft.Padding(0, 0, 0, 20),
        )

        # 附件区
        attach_section = ft.Container(visible=False)
        if mail.attachments:
            attach_list = ft.Row(spacing=12, wrap=True)
            total_size = sum(a.size for a in mail.attachments)
            attach_title = ft.Row(
                [
                    ft.Text(
                        "附件",
                        size=Font.BODY_SM,
                        weight=ft.FontWeight.W_600,
                        color=c.TEXT_PRIMARY,
                    ),
                    ft.Text(
                        f"({len(mail.attachments)} 个文件 · 共 {_format_size(total_size)})",
                        size=Font.SMALL,
                        color=c.TEXT_PLACEHOLDER,
                    ),
                ],
                spacing=6,
            )
            for att in mail.attachments:
                attach_list.controls.append(self._build_attachment_card(att))

            attach_section = ft.Container(
                content=ft.Column(
                    [attach_title, attach_list],
                    spacing=12,
                ),
                padding=ft.Padding(0, 20, 0, 0),
                border=ft.Border(top=ft.border.BorderSide(1, c.BORDER_LIGHT)),
                margin=ft.Margin(0, 28, 0, 0),
            )

        return ft.Column(
            [
                subject,
                tags_container,
                sender_section,
                body_section,
                attach_section,
            ],
            spacing=0,
        )

    def _build_attachment_card(self, att) -> ft.Container:
        """附件卡片（200px 宽 + 预览图 + 文件名 + 大小）"""
        c = self._colors
        ext = ""
        if "." in att.filename:
            ext = "." + att.filename.rsplit(".", 1)[-1].lower()

        preset = ATTACH_PRESETS.get(ext, ("ATTACH_XLS_GRADIENT", "FILE", "rgba(37,99,235,0.9)"))
        grad_attr, label, text_color = preset
        gradient_colors = getattr(c, grad_attr)

        # 文件类型标签
        type_label = ext.lstrip(".").upper()[:4] if ext else "FILE"

        return ft.Container(
            content=ft.Column(
                [
                    # 预览区（100px 高）
                    ft.Container(
                        content=ft.Text(
                            type_label,
                            size=16,
                            color=text_color,
                            weight=ft.FontWeight.W_700,
                        ),
                        width=200,
                        height=100,
                        alignment=ft.Alignment(0, 0),
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment(-1, -1),
                            end=ft.Alignment(1, 1),
                            colors=gradient_colors,
                        ),
                    ),
                    # 文件信息
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    att.filename,
                                    size=Font.BODY_SM,
                                    color=c.TEXT_PRIMARY,
                                    weight=ft.FontWeight.W_500,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    f"{type_label} · {_format_size(att.size)}",
                                    size=Font.SMALL,
                                    color=c.TEXT_PLACEHOLDER,
                                ),
                            ],
                            spacing=2,
                        ),
                        padding=ft.Padding(12, 10, 12, 10),
                    ),
                ],
                spacing=0,
            ),
            width=200,
            border_radius=Radius.CARD,
            border=ft.Border.all(1, c.BORDER),
            ink=True,
        )

    # ---- 回复区 ----
    def _build_reply_section(self) -> ft.Container:
        """底部回复区（快捷操作 + 工具栏 + 输入框 + 发送按钮）"""
        c = self._colors

        def make_quick_action(label):
            return ft.Container(
                content=ft.Text(
                    label,
                    size=Font.BODY_SM,
                    color=c.TEXT_PRIMARY,
                ),
                padding=ft.Padding(16, 8, 16, 8),
                border=ft.Border.all(1, c.BORDER),
                border_radius=Radius.CARD,
                bgcolor=c.BG_MAIN,
                ink=True,
            )

        quick_actions = ft.Row(
            [
                make_quick_action("回复"),
                make_quick_action("全部回复"),
                make_quick_action("转发"),
            ],
            spacing=4,
        )

        # 回复工具栏
        def make_reply_btn(icon, label):
            return ft.Container(
                content=ft.Icon(icon, size=14, color=c.TEXT_SECONDARY),
                tooltip=label,
                padding=ft.Padding(6, 4, 6, 4),
                border_radius=Radius.BUTTON,
                ink=True,
            )

        reply_toolbar = ft.Row(
            [
                make_reply_btn(ft.Icons.FORMAT_BOLD, "加粗"),
                make_reply_btn(ft.Icons.FORMAT_ITALIC, "斜体"),
                make_reply_btn(ft.Icons.FORMAT_UNDERLINED, "下划线"),
                make_reply_btn(ft.Icons.LIST, "列表"),
                make_reply_btn(ft.Icons.FORMAT_LIST_NUMBERED, "有序列表"),
                make_reply_btn(ft.Icons.LINK, "链接"),
                make_reply_btn(ft.Icons.EMOJI_EMOTIONS_OUTLINED, "表情"),
                ft.Container(expand=True),
                make_reply_btn(ft.Icons.ATTACHMENT, "附件"),
                make_reply_btn(ft.Icons.IMAGE_OUTLINED, "图片"),
            ],
            spacing=2,
        )

        # 回复输入框
        reply_input = ft.Container(
            content=ft.Text(
                "点击此处输入回复内容... （Ctrl + Enter 发送）",
                size=Font.BODY,
                color=c.TEXT_PLACEHOLDER,
            ),
            padding=ft.Padding(16, 14, 16, 14),
            height=60,
            alignment=ft.Alignment(-1, -1),
        )

        # 发送按钮
        send_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.SEND, size=14, color=c.TEXT_ON_PRIMARY),
                    ft.Text(
                        "发送",
                        size=Font.BODY_SM,
                        color=c.TEXT_ON_PRIMARY,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.Padding(20, 8, 20, 8),
            border_radius=Radius.BUTTON,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0),
                end=ft.Alignment(1, 0),
                colors=c.COMPOSE_GRADIENT,
            ),
            ink=True,
        )

        reply_footer = ft.Row(
            [
                send_btn,
                ft.Container(expand=True),
                ft.Container(
                    content=ft.Text("定时", size=Font.AUX, color=c.TEXT_SECONDARY),
                    tooltip="定时发送",
                    padding=ft.Padding(8, 4, 8, 4),
                    ink=True,
                ),
                ft.Container(
                    content=ft.Text("草稿", size=Font.AUX, color=c.TEXT_SECONDARY),
                    tooltip="存草稿",
                    padding=ft.Padding(8, 4, 8, 4),
                    ink=True,
                ),
                ft.Container(
                    content=ft.Text("丢弃", size=Font.AUX, color=c.TEXT_SECONDARY),
                    tooltip="丢弃",
                    padding=ft.Padding(8, 4, 8, 4),
                    ink=True,
                ),
            ],
            spacing=8,
        )

        # 输入框 wrapper
        input_wrap = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=reply_toolbar,
                        padding=ft.Padding(12, 8, 12, 8),
                        border=ft.Border(bottom=ft.border.BorderSide(1, c.BORDER_LIGHT)),
                    ),
                    reply_input,
                    ft.Container(
                        content=reply_footer,
                        padding=ft.Padding(14, 10, 14, 10),
                        border=ft.Border(top=ft.border.BorderSide(1, c.BORDER_LIGHT)),
                        bgcolor=c.BG_REPLY,
                    ),
                ],
                spacing=0,
            ),
            border=ft.Border.all(1, c.BORDER),
            border_radius=Radius.CARD,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        return ft.Container(
            content=ft.Column(
                [quick_actions, input_wrap],
                spacing=12,
            ),
            padding=ft.Padding(24, 16, 24, 20),
            border=ft.Border(top=ft.border.BorderSide(1, c.BORDER_LIGHT)),
            bgcolor=c.BG_REPLY,
        )

    # ---- 显示邮件 ----
    def show_mail(self, mail: MailData):
        """显示邮件详情"""
        self._current_mail = mail
        c = self._colors

        self._empty_view.visible = False
        self._detail_view.visible = True

        # 重建详情内容
        self._content_scroll.controls.clear()
        detail_content = self._build_detail_content()
        # 外层加 padding 28px 36px
        self._content_scroll.controls.append(
            ft.Container(
                content=detail_content,
                padding=ft.Padding(36, 28, 36, 20),
            )
        )

        logger.info(f"显示邮件详情: {mail.subject}")
        self.update()

    # ---- 操作回调（占位） ----
    def _on_back(self, e=None):
        logger.info("点击返回")

    def _on_archive(self, e=None):
        logger.info("点击归档")

    def _on_delete(self, e=None):
        logger.info("点击删除")

    def _on_mark_unread(self, e=None):
        logger.info("点击标记未读")

    def _on_move(self, e=None):
        logger.info("点击移动到")

    def _on_label(self, e=None):
        logger.info("点击标签")

    def _on_more(self, e=None):
        logger.info("点击更多")

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
        self._build()
        if self._current_mail:
            self.show_mail(self._current_mail)
        else:
            self.update()
