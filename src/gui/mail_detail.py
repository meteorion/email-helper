"""邮件详情组件 - Flet 实现（第四栏）

严格对齐 email_desktop_ui_design.html 设计稿：
  - 顶部工具栏：图标按钮（返回/归档/删除/标记未读/移动/标签/更多）
  - 详情内容（padding 28px 36px）：
      大标题 24px Bold + 标签
      发件人区（48px 圆形渐变头像 + 姓名/邮箱/收件人 + 时间）
      正文 Markdown 渲染 + 引用折叠
      附件卡片（分色渐变 + 预览图 + 文件名 + 大小）
  - 底部回复区：快捷操作 + TextField 输入框 + 发送按钮
"""

import re
from email.header import decode_header as _rfc2047_decode
from html.parser import HTMLParser

import flet as ft

from src.core.models import MailData
from src.core.logger import get_logger
from src.gui.theme import Color, DarkColor, Radius, Font, TAG_COLOR_MAP

logger = get_logger("gui.mail_detail")

# 引用邮件分隔符（企业邮/QQ邮/标准 > 引用）
_QUOTE_SEP_RE = re.compile(
    r"(?m)^(?:"
    r"发件人[:：][ \t]|"           # 企业邮 / Coremail
    r"From:[ \t]|"                 # 英文
    r"-{4,}|"                      # ---- 原始邮件 ---- 等
    r".{0,20}在\d{4}年\d+月\d+日.{0,40}写道[:：]"  # "X 在 2026年8月4日 写道："
    r")",
)


class _HtmlToText(HTMLParser):
    """将 HTML 转为可读纯文本，保留段落结构，忽略 style/script。"""
    # 结束时触发换行的块级标签
    _BLOCK_END = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6",
                  "tr", "blockquote", "section", "article"}
    _SKIP = {"style", "script", "head", "svg"}

    def __init__(self):
        super().__init__()
        self._buf: list[str] = []
        self._skip_depth = 0

    def _ensure_newline(self):
        """确保缓冲区以换行结尾，避免重复添加。"""
        joined = "".join(self._buf)
        if joined and not joined[-1] == "\n":
            self._buf.append("\n")

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif not self._skip_depth and tag == "br":
            self._ensure_newline()

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif not self._skip_depth and tag in self._BLOCK_END:
            self._ensure_newline()

    def handle_data(self, data):
        if not self._skip_depth:
            self._buf.append(data)

    def handle_entityref(self, name):
        import html as _html
        if not self._skip_depth:
            self._buf.append(_html.unescape(f"&{name};"))

    def handle_charref(self, name):
        import html as _html
        if not self._skip_depth:
            self._buf.append(_html.unescape(f"&#{name};"))

    def get_text(self) -> str:
        raw = "".join(self._buf)
        # 逐行清理行内多余空白
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in raw.splitlines()]
        text = "\n".join(lines)
        # 最多保留一个空行
        text = re.sub(r"\n{2,}", "\n\n", text)
        return text.strip()


def _html_to_text(html: str) -> str:
    parser = _HtmlToText()
    try:
        parser.feed(html)
        return parser.get_text()
    except Exception:
        return re.sub(r"<[^>]+>", "", html).strip()


def _split_body(text: str) -> tuple[str, str]:
    """拆分正文为 (主内容, 引用内容)，识别 > 前缀和中文常见引用分隔符"""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.lstrip().startswith(">"):
            return "\n".join(lines[:i]).strip(), "\n".join(lines[i:]).strip()
    m = _QUOTE_SEP_RE.search(text)
    if m:
        line_start = text.rfind("\n", 0, m.start()) + 1
        return text[:line_start].strip(), text[line_start:].strip()
    return text.strip(), ""


# 附件扩展名 → 预览配置：(渐变色属性, 预览标签, 文字色, 大小信息类型名)
ATTACH_PRESETS = {
    ".pdf": ("ATTACH_PDF_GRADIENT", "PDF", "#DC2626", "PDF"),
    ".doc": ("ATTACH_XLS_GRADIENT", "DOC", "#2563EB", "Word"),
    ".docx": ("ATTACH_XLS_GRADIENT", "DOC", "#2563EB", "Word"),
    ".xls": ("ATTACH_XLS_GRADIENT", "XLS", "#2563EB", "Excel"),
    ".xlsx": ("ATTACH_XLS_GRADIENT", "XLS", "#2563EB", "Excel"),
    ".ppt": ("ATTACH_XLS_GRADIENT", "PPT", "#2563EB", "PowerPoint"),
    ".pptx": ("ATTACH_XLS_GRADIENT", "PPT", "#2563EB", "PowerPoint"),
    ".zip": ("ATTACH_ZIP_GRADIENT", "ZIP", "#EA580C", "压缩包"),
    ".rar": ("ATTACH_ZIP_GRADIENT", "ZIP", "#EA580C", "压缩包"),
    ".7z": ("ATTACH_ZIP_GRADIENT", "7Z", "#EA580C", "压缩包"),
    ".png": ("ATTACH_IMG_GRADIENT", "IMG", "#16A34A", "图片"),
    ".jpg": ("ATTACH_IMG_GRADIENT", "IMG", "#16A34A", "图片"),
    ".jpeg": ("ATTACH_IMG_GRADIENT", "IMG", "#16A34A", "图片"),
    ".gif": ("ATTACH_IMG_GRADIENT", "GIF", "#16A34A", "图片"),
    ".svg": ("ATTACH_IMG_GRADIENT", "SVG", "#16A34A", "图片"),
}


def _decode_rfc2047(text: str) -> str:
    """解码 RFC2047 编码的邮件头"""
    try:
        parts = _rfc2047_decode(text)
        result = ""
        for part, charset in parts:
            if isinstance(part, bytes):
                result += part.decode(charset or "utf-8", errors="replace")
            else:
                result += part
        return result.strip()
    except Exception:
        return text


def _extract_sender(sender: str) -> tuple[str, str]:
    """从 sender 提取 (显示名, 邮箱)，自动解码 RFC2047"""
    sender = _decode_rfc2047(sender)
    if "<" in sender and ">" in sender:
        name = sender.split("<")[0].strip().strip('"').strip()
        email = sender.split("<")[1].split(">")[0].strip()
        if not name or name == email:
            name = email.split("@")[0] if "@" in email else email
        return (name, email)
    if "@" in sender and " " not in sender:
        return (sender.split("@")[0], sender)
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
    """格式化时间，兼容 timezone-aware datetime"""
    from datetime import datetime, timedelta
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
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
                    ft.Container(
                        content=ft.Icon(ft.Icons.MAIL_OUTLINE, size=48, color=c.TEXT_PLACEHOLDER),
                        width=96, height=96,
                        border_radius=50,
                        bgcolor=c.BG_HOVER,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        "查看邮件详情",
                        size=20,
                        weight=ft.FontWeight.W_600,
                        color=c.TEXT_SECONDARY,
                    ),
                    ft.Text(
                        "从左侧列表选择一封邮件，即可在此查看完整内容",
                        size=Font.BODY_SM,
                        color=c.TEXT_PLACEHOLDER,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
            ),
            expand=True,
            alignment=ft.Alignment(0, 0),
        )

        # 详情容器（工具栏 + 滚动内容）
        self._toolbar = self._build_toolbar()
        self._content_scroll = ft.Column(
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        self._detail_view = ft.Column(
            [self._toolbar, self._content_scroll],
            spacing=0,
            expand=True,
            visible=False,
        )

        self.controls = [self._empty_view, self._detail_view]

    # ---- 工具栏 ----
    def _build_toolbar(self) -> ft.Container:
        """顶部工具栏（图标按钮 + 更多菜单）"""
        c = self._colors

        def make_icon_btn(icon, tooltip, on_click=None, danger=False):
            """图标按钮（hover 背景高亮）"""
            icon_color = c.ERROR if danger else c.TEXT_SECONDARY
            return ft.Container(
                content=ft.Icon(icon, size=18, color=icon_color),
                width=32, height=32,
                border_radius=8,
                tooltip=tooltip,
                ink=True,
                on_hover=lambda e: (
                    setattr(e.control, 'bgcolor', c.BG_HOVER) if e.data == 'true'
                    else setattr(e.control, 'bgcolor', None),
                    e.control.update() if e.control.page else None,
                ),
                on_click=on_click,
            )

        # 分隔线
        separator = ft.Container(
            width=1, height=20,
            bgcolor=c.BORDER,
            margin=ft.Margin(6, 0, 6, 0),
        )

        return ft.Container(
            content=ft.Row(
                [
                    make_icon_btn(ft.Icons.ARROW_BACK, "返回", self._on_back),
                    make_icon_btn(ft.Icons.ARCHIVE_OUTLINED, "归档", self._on_archive),
                    make_icon_btn(ft.Icons.DELETE_OUTLINE, "删除", self._on_delete, danger=True),
                    separator,
                    make_icon_btn(ft.Icons.MARK_EMAIL_UNREAD_OUTLINED, "标记未读", self._on_mark_unread),
                    make_icon_btn(ft.Icons.DRIVE_FILE_MOVE_OUTLINED, "移动到", self._on_move),
                    make_icon_btn(ft.Icons.LABEL_OUTLINED, "标签", self._on_label),
                    ft.Container(expand=True),
                    make_icon_btn(ft.Icons.MORE_VERT, "更多", self._on_more),
                ],
                spacing=2,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(20, 10, 20, 10),
            border=ft.Border(bottom=ft.border.BorderSide(1, c.BORDER_LIGHT)),
        )

    # ---- 详情内容 ----
    def _build_mail_header(self, mail: MailData) -> ft.Column:
        """邮件头部：大标题 + 标签 + 发件人区（不含正文/附件）"""
        c = self._colors
        sender_name, sender_email = _extract_sender(mail.sender)
        avatar_letter = _get_avatar_letter(sender_name)

        subject = ft.Text(
            mail.subject or "(无主题)",
            size=Font.DETAIL_SUBJECT,
            weight=ft.FontWeight.W_700,
            color=c.TEXT_PRIMARY,
        )

        tag_row = ft.Row(spacing=8)
        if mail.tags:
            for tag in mail.tags[:5]:
                bg, txt = _get_tag_colors(tag, c)
                tag_row.controls.append(ft.Container(
                    content=ft.Text(tag, size=Font.TINY, color=txt, weight=ft.FontWeight.W_500),
                    bgcolor=bg, border_radius=Radius.TAB, padding=ft.Padding(8, 2, 8, 2),
                ))
        if mail.priority == "high":
            bg, txt = c.TAG_HIGH
            tag_row.controls.append(ft.Container(
                content=ft.Text("高优先级", size=Font.TINY, color=txt, weight=ft.FontWeight.W_500),
                bgcolor=bg, border_radius=Radius.TAB, padding=ft.Padding(8, 2, 8, 2),
            ))
        tags_container = ft.Container(
            content=tag_row, margin=ft.Margin(0, 0, 0, 24), visible=bool(tag_row.controls),
        )

        sender_avatar = ft.Container(
            content=ft.Text(avatar_letter, size=18, color=c.TEXT_ON_PRIMARY, weight=ft.FontWeight.W_700),
            width=48, height=48, border_radius=50, alignment=ft.Alignment(0, 0),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), colors=c.AVATAR_GRADIENT_2,
            ),
        )
        sender_email_text = (
            ft.Text(sender_email, size=Font.BODY_SM, color=c.TEXT_SECONDARY)
            if sender_email else ft.Container()
        )
        meta_row = ft.Row([
            ft.Text("收件人：", size=Font.AUX, color=c.TEXT_PLACEHOLDER),
            ft.Text(mail.recipient or "我", size=Font.AUX, color=c.TEXT_SECONDARY),
        ], spacing=0)
        time_text = ft.Text(_format_time(mail.send_time), size=Font.BODY_SM, color=c.TEXT_SECONDARY)
        attach_count_text = (
            ft.Text(f"{len(mail.attachments)} 个附件", size=Font.SMALL, color=c.TEXT_SECONDARY)
            if mail.attachments else ft.Container()
        )
        sender_section = ft.Container(
            content=ft.Row([
                sender_avatar,
                ft.Column(
                    [ft.Text(sender_name, size=Font.BODY_LG, weight=ft.FontWeight.W_600, color=c.TEXT_PRIMARY),
                     sender_email_text, meta_row],
                    spacing=4, expand=True,
                ),
                ft.Column([time_text, attach_count_text], spacing=2,
                          horizontal_alignment=ft.CrossAxisAlignment.END),
            ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START),
            padding=ft.Padding(0, 16, 0, 16),
            border=ft.Border(
                top=ft.border.BorderSide(1, c.BORDER_LIGHT),
                bottom=ft.border.BorderSide(1, c.BORDER_LIGHT),
            ),
            margin=ft.Margin(0, 0, 0, 0),
        )
        return ft.Column([subject, tags_container, sender_section], spacing=0)

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

        # 收件人信息（仅展示真实数据）
        meta_row = ft.Row(
            [
                ft.Text("收件人：", size=Font.AUX, color=c.TEXT_PLACEHOLDER),
                ft.Text(mail.recipient or "我", size=Font.AUX, color=c.TEXT_SECONDARY),
            ],
            spacing=0,
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
                            sender_name_text,
                            sender_email_text,
                            meta_row,
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

        body_section = self._build_body_section(mail)

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

    # ---- 正文 + 引用 ----

    def _build_body_section(self, mail: MailData) -> ft.Container:
        """构建正文区：优先用 body_html 转文本渲染，降级到 body_text"""
        c = self._colors

        # HTML 优先：转为纯文本后展示（保留段落结构）
        if (mail.body_html or "").strip():
            text = _html_to_text(mail.body_html or "")
            inner = ft.Text(text, selectable=True, no_wrap=False,
                            size=Font.BODY, color=c.TEXT_PRIMARY)
            return ft.Container(content=inner, padding=ft.Padding(0, 0, 0, 20))

        raw = (mail.body_text or "").strip()
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        raw = re.sub(r"\n{3,}", "\n\n", raw)

        main_text, quoted_text = _split_body(raw)

        parts: list = []

        if main_text:
            parts.append(ft.Markdown(
                main_text,
                selectable=True,
                auto_follow_links=True,
            ))

        # ── 引用内容：点击时才创建 widget（完全懒加载）──
        if quoted_text:
            parts.append(self._build_quote_widget(quoted_text))

        inner = ft.Column(parts, spacing=16) if parts else ft.Container()
        return ft.Container(content=inner, padding=ft.Padding(0, 0, 0, 20))

    def _build_quote_widget(self, text: str) -> ft.Column:
        """引用邮件块：点击时才创建内容 widget（完全懒加载）"""
        c = self._colors
        is_dark = self._is_dark

        quote_bg     = "#F1F5F9" if not is_dark else "#1E293B"
        quote_border = "#CBD5E1" if not is_dark else "#475569"
        quote_fg     = "#64748B" if not is_dark else "#94A3B8"
        btn_fg       = "#94A3B8" if not is_dark else "#64748B"

        MAX_QUOTE = 800

        quote_slot = ft.Column([], spacing=0)   # 展开时才填入内容
        expanded   = [False]

        toggle_label = ft.Text(
            "▶  查看引用邮件",
            size=Font.AUX,
            color=btn_fg,
            weight=ft.FontWeight.W_500,
        )

        def _on_toggle(e, qt=text):
            expanded[0] = not expanded[0]
            if expanded[0]:
                display = qt[:MAX_QUOTE] + ("\n\n*…（内容过长已截断）*" if len(qt) > MAX_QUOTE else "")
                quote_slot.controls = [ft.Container(
                    content=ft.Markdown(
                        display,
                        selectable=True,
                    ),
                    padding=ft.Padding(12, 10, 12, 10),
                    bgcolor=quote_bg,
                    border=ft.Border(left=ft.border.BorderSide(3, quote_border)),
                    border_radius=ft.BorderRadius(0, 4, 0, 4),
                )]
                toggle_label.value = "▼  收起引用"
            else:
                quote_slot.controls = []
                toggle_label.value = "▶  查看引用邮件"
            self.update()

        toggle_btn = ft.Container(
            content=toggle_label,
            on_click=_on_toggle,
            padding=ft.Padding(0, 6, 0, 2),
            ink=True,
        )

        return ft.Column([toggle_btn, quote_slot], spacing=6)

    def _build_attachment_card(self, att) -> ft.Container:
        """附件卡片（200px 宽 + 预览图 + 文件名 + 大小）"""
        c = self._colors
        ext = ""
        if "." in att.filename:
            ext = "." + att.filename.rsplit(".", 1)[-1].lower()

        preset = ATTACH_PRESETS.get(ext, ("ATTACH_XLS_GRADIENT", "FILE", "#6B7280", "文件"))
        grad_attr, label, text_color, size_type = preset
        gradient_colors = getattr(c, grad_attr)

        return ft.Container(
            content=ft.Column(
                [
                    # 预览区（100px 高，渐变背景 + 类型标签）
                    ft.Container(
                        content=ft.Text(
                            label,
                            size=16,
                            color=text_color,
                            weight=ft.FontWeight.W_700,
                        ),
                        height=80,
                        alignment=ft.Alignment(0, 0),
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment(-1, -1),
                            end=ft.Alignment(1, 1),
                            colors=gradient_colors,
                        ),
                        expand=True,
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
                                    f"{size_type} · {_format_size(att.size)}",
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
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ink=True,
        )

    # ---- 显示邮件 ----
    def show_mail(self, mail: MailData):
        """显示邮件详情"""
        self._current_mail = mail

        self._empty_view.visible = False
        self._detail_view.visible = True

        self._content_scroll.scroll = ft.ScrollMode.AUTO
        self._content_scroll.controls.clear()
        detail_content = self._build_detail_content()
        self._content_scroll.controls.append(
            ft.Container(content=detail_content, padding=ft.Padding(36, 28, 36, 20))
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
