"""邮件列表组件 - Flet 实现（第三栏 380px）

严格对齐 email_desktop_ui_design.html 设计稿：
  - 标题区（18px 标题 + 拉取按钮）
  - 搜索框（圆角 18px 胶囊，placeholder "搜索邮件、联系人、内容..."）
  - 筛选 Tab（全部/未读，下划线选中）
  - 邮件项：复选框 + 星标 + 发件人头像/名 + 时间 + 主题 + 预览 + 标签
  - 未读：左侧 3px 蓝边 + 浅蓝背景 + 发件人加粗
  - 选中：深蓝背景
"""

from datetime import datetime, timedelta, timezone
from email.header import decode_header as _rfc2047_decode

import flet as ft

from src.core.models import MailData
from src.core.logger import get_logger
from src.gui.theme import Color, DarkColor, Radius, Font, TAG_COLOR_MAP

logger = get_logger("gui.mail_list")


# 筛选 Tab 定义
FILTER_TABS = [
    ("all", "全部"),
    ("unread", "未读"),
]


def _decode_rfc2047(text: str) -> str:
    """解码 RFC2047 编码的邮件头（=?UTF-8?B?...?= 或 =?GBK?Q?...?=）"""
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


def _extract_sender_name(sender: str) -> str:
    """从 sender 字段提取可读显示名，自动解码 RFC2047 编码"""
    sender = _decode_rfc2047(sender)
    if "<" in sender and ">" in sender:
        name = sender.split("<")[0].strip().strip('"').strip()
        email_part = sender.split("<")[1].split(">")[0].strip()
        # 显示名为空或与邮箱相同时，取邮箱用户名前缀
        if not name or name == email_part:
            return email_part.split("@")[0] if "@" in email_part else email_part
        return name
    # 纯邮箱地址：显示 @ 前缀
    if "@" in sender and " " not in sender:
        return sender.split("@")[0]
    return sender.strip().strip('"')


def _format_time(dt: datetime) -> str:
    """格式化时间显示（相对时间），兼容 timezone-aware datetime"""
    # 统一转为本地 naive datetime 再比较
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    now = datetime.now()
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    elif dt.date() == (now - timedelta(days=1)).date():
        return "昨天"
    elif (now - dt).days < 7:
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return weekdays[dt.weekday()]
    else:
        return dt.strftime("%m月%d日")


def _get_tag_colors(tag: str, colors):
    """根据标签名获取颜色 (bg, text)"""
    attr = "TAG_" + TAG_COLOR_MAP.get(tag, "PROJECT")
    return getattr(colors, attr)


@ft.control("Column", init=False)
class MailListView(ft.Column):
    """邮件列表视图"""

    def __init__(self, on_select=None, on_fetch=None, is_dark: bool = False,
                 on_mark_read=None, on_mark_unread=None, on_star=None,
                 on_delete=None, on_reply=None, on_forward=None,
                 on_move=None, on_export=None):
        super().__init__()
        self.spacing = 0
        self.expand = True
        self._on_select = on_select
        self._on_fetch = on_fetch
        self._is_dark = is_dark
        # 右键菜单（更多操作）回调
        # 外部回调（前缀 _cb_，避免与同名实例方法冲突）
        self._cb_mark_read = on_mark_read
        self._cb_mark_unread = on_mark_unread
        self._cb_star = on_star
        self._cb_delete = on_delete
        self._cb_reply = on_reply
        self._cb_forward = on_forward
        self._cb_move = on_move
        self._cb_export = on_export
        self._mails: list[MailData] = []
        self._filtered: list[MailData] = []
        self._selected_id: str | None = None
        self._current_filter = "all"
        self._search_keyword = ""
        self._fetching = False

        self._build()

    @property
    def _colors(self):
        return DarkColor if self._is_dark else Color

    # ---- 构建 UI ----
    def _build(self):
        c = self._colors
        # 标题
        self._title = ft.Text(
            "收件箱",
            size=Font.PANEL_TITLE,
            weight=ft.FontWeight.W_600,
            color=c.TEXT_PRIMARY,
        )
        # 拉取按钮
        self._fetch_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.REFRESH, size=14, color=c.PRIMARY_700),
                    ft.Text(
                        "拉取" if not self._fetching else "拉取中...",
                        size=Font.AUX,
                        color=c.PRIMARY_700,
                        weight=ft.FontWeight.W_500,
                    ),
                ],
                spacing=4,
            ),
            on_click=self._on_fetch_click,
            padding=ft.Padding(10, 5, 10, 5),
            border_radius=Radius.BUTTON,
            ink=True,
        )

        # 搜索框
        self._search_input = ft.TextField(
            hint_text="搜索邮件、联系人、内容...",
            text_size=Font.AUX,
            border_radius=18,
            border_color=c.BORDER,
            bgcolor=c.BG_HOVER,
            focused_border_color=c.PRIMARY_500,
            focused_bgcolor=c.BG_MAIN,
            height=36,
            content_padding=ft.Padding(14, 0, 14, 0),
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._on_search_change,
        )

        # 筛选 Tab 容器
        self._filter_tabs_row = self._build_filter_tabs()

        # 邮件列表区（可滚动）
        self._mail_items_col = ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.AUTO)

        # 空状态
        self._empty_view = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.INBOX_OUTLINED, size=48, color=c.TEXT_PLACEHOLDER),
                    ft.Text(
                        "暂无邮件",
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
            visible=False,
        )

        self.controls = [
            # 标题区
            ft.Container(
                content=ft.Row(
                    [self._title, ft.Container(expand=True), self._fetch_btn],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=ft.Padding(20, 16, 20, 12),
            ),
            # 搜索框
            ft.Container(
                content=self._search_input,
                padding=ft.Padding(20, 0, 20, 12),
            ),
            # 筛选 Tab
            self._filter_tabs_row,
            # 分割线
            ft.Container(height=1, bgcolor=c.BORDER_LIGHT),
            # 邮件列表
            self._mail_items_col,
            self._empty_view,
        ]

    def _build_filter_tabs(self) -> ft.Container:
        """筛选 Tab 行"""
        c = self._colors
        tabs = []
        for key, label in FILTER_TABS:
            is_active = (key == self._current_filter)
            tab = ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            label,
                            size=Font.BODY_SM,
                            color=c.PRIMARY_700 if is_active else c.TEXT_SECONDARY,
                            weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_400,
                        ),
                        ft.Container(
                            width=24,
                            height=2,
                            bgcolor=c.PRIMARY_700 if is_active else None,
                            border_radius=1,
                        ),
                    ],
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                data=key,
                on_click=self._on_filter_click,
                padding=ft.Padding(0, 8, 20, 8),
            )
            tabs.append(tab)

        return ft.Container(
            content=ft.Row(tabs, spacing=0),
            padding=ft.Padding(20, 0, 0, 0),
            border=ft.Border(bottom=ft.border.BorderSide(1, c.BORDER_LIGHT)),
        )

    # ---- 邮件项构建 ----
    def _build_mail_item(self, mail: MailData) -> ft.Container:
        """构建单个邮件项"""
        c = self._colors
        is_unread = not mail.is_read
        is_selected = (mail.message_id == self._selected_id)

        # 背景色优先级：selected > unread > normal
        if is_selected:
            bgcolor = c.BG_SELECTED
        elif is_unread:
            bgcolor = c.BG_UNREAD
        else:
            bgcolor = None

        # 左侧未读竖条
        left_border_color = c.PRIMARY_500 if is_unread else None

        sender_name = _extract_sender_name(mail.sender)

        # 复选框（对齐设计稿 .email-checkbox：16x16 圆角方框）
        checkbox = ft.Container(
            width=16,
            height=16,
            border_radius=Radius.TAB,
            border=ft.Border.all(1.5, c.BORDER),
        )

        # 星标
        is_starred = "星标" in (mail.tags or []) or mail.priority == "high"
        star_color = c.STAR if is_starred else c.BORDER
        star = ft.Icon(
            ft.Icons.STAR if is_starred else ft.Icons.STAR_BORDER,
            size=16,
            color=star_color,
        )

        # 发件人名
        sender_weight = ft.FontWeight.W_700 if is_unread else ft.FontWeight.W_500
        sender_color = c.TEXT_PRIMARY if is_unread else c.TEXT_PRIMARY
        sender_text = ft.Text(
            sender_name,
            size=Font.BODY,
            color=sender_color,
            weight=sender_weight,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
        )

        # 时间
        time_color = c.PRIMARY_700 if is_unread else c.TEXT_PLACEHOLDER
        time_weight = ft.FontWeight.W_500 if is_unread else ft.FontWeight.W_400
        time_text = ft.Text(
            _format_time(mail.send_time),
            size=Font.AUX,
            color=time_color,
            weight=time_weight,
        )

        # ── 更多操作按钮（替代右键菜单） ──
        more_menu = self._build_mail_menu(mail)

        # 主题
        subject_weight = ft.FontWeight.W_700 if is_unread else ft.FontWeight.W_500
        subject_color = c.TEXT_PRIMARY if is_unread else c.TEXT_PRIMARY
        subject_text = ft.Text(
            mail.subject or "(无主题)",
            size=Font.BODY_SM,
            color=subject_color,
            weight=subject_weight,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # 预览（取 body_text 前 60 字）
        preview = (mail.body_text or "")[:60].replace("\n", " ").strip()
        preview_text = ft.Text(
            preview,
            size=Font.AUX,
            color=c.TEXT_SECONDARY,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # 标签
        tag_row = ft.Row(spacing=6)
        if mail.tags:
            for tag in mail.tags[:3]:
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

        # 顶部行：复选框 + 星标 + 发件人 + 时间 + 更多菜单
        top_row = ft.Row(
            [checkbox, star, sender_text, time_text, more_menu],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 主题行（左缩进 40px，对齐设计稿 padding-left:40px）
        subject_row = ft.Container(
            content=subject_text,
            padding=ft.Padding(40, 0, 0, 0),
        )

        # 预览行
        preview_row = ft.Container(
            content=preview_text,
            padding=ft.Padding(40, 0, 0, 0),
            margin=ft.Margin(0, 2, 0, 0),
        )

        # 标签行（仅有标签时显示）
        tags_container = ft.Container(
            content=tag_row,
            padding=ft.Padding(40, 0, 0, 0),
            margin=ft.Margin(0, 6, 0, 0),
            visible=bool(mail.tags),
        )

        item = ft.Container(
            content=ft.Column(
                [top_row, subject_row, preview_row, tags_container],
                spacing=4,
            ),
            data=mail.message_id,
            on_click=self._on_mail_click,
            padding=ft.Padding(20, 14, 20, 14),
            border=ft.Border(
                left=ft.border.BorderSide(3, left_border_color) if left_border_color
                else ft.border.BorderSide(3, "transparent"),
                bottom=ft.border.BorderSide(1, c.BORDER_LIGHT),
            ),
            bgcolor=bgcolor,
            ink=True,
        )
        return item

    def _build_mail_menu(self, mail: MailData) -> ft.PopupMenuButton:
        """构建单个邮件的更多操作菜单（替代右键菜单）"""
        c = self._colors
        mid = mail.message_id
        is_starred = "星标" in (mail.tags or []) or mail.priority == "high"

        # 图标颜色（按功能分组）
        CLR_BLUE = c.PRIMARY_500
        CLR_AMBER = "#F59E0B"
        CLR_GREEN = "#10B981"
        CLR_PURPLE = "#8B5CF6"
        CLR_RED = "#EF4444"

        def _menu_item(icon, icon_color, label, on_click, text_color=None):
            """统一构建带彩色图标的菜单项"""
            return ft.PopupMenuItem(
                content=ft.Row(
                    [
                        ft.Icon(icon, size=18, color=icon_color),
                        ft.Text(
                            label,
                            size=13,
                            color=text_color or c.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_400,
                        ),
                    ],
                    spacing=12,
                ),
                on_click=on_click,
            )

        menu_items = [
            # ── 第一组：状态标记 ──
            _menu_item(
                ft.Icons.MARK_EMAIL_READ if mail.is_read else ft.Icons.MARKUNREAD_MAILBOX,
                CLR_BLUE,
                "标记未读" if mail.is_read else "标记已读",
                lambda e, m=mid: (
                    self._on_mark_unread(m) if mail.is_read else self._on_mark_read(m)
                ),
            ),
            _menu_item(
                ft.Icons.STAR if is_starred else ft.Icons.STAR_BORDER,
                CLR_AMBER,
                "取消星标" if is_starred else "加星标",
                lambda e, m=mid: self._on_star_toggle(m),
            ),
            ft.PopupMenuItem(),  # 分隔线
            # ── 第二组：快速操作 ──
            _menu_item(ft.Icons.REPLY, CLR_GREEN, "回复",
                       lambda e, m=mid: self._on_reply(m)),
            _menu_item(ft.Icons.FORWARD, CLR_GREEN, "转发",
                       lambda e, m=mid: self._on_forward(m)),
            ft.PopupMenuItem(),  # 分隔线
            # ── 第三组：整理 ──
            _menu_item(ft.Icons.DRIVE_FILE_MOVE, CLR_PURPLE, "移动到...",
                       lambda e, m=mid: self._on_move(m)),
            _menu_item(ft.Icons.FILE_DOWNLOAD, CLR_PURPLE, "导出邮件",
                       lambda e, m=mid: self._on_export(m)),
            ft.PopupMenuItem(),  # 分隔线
            # ── 第四组：危险操作 ──
            _menu_item(ft.Icons.DELETE_OUTLINE, CLR_RED, "删除",
                       lambda e, m=mid: self._on_delete(m),
                       text_color=CLR_RED),
        ]

        return ft.PopupMenuButton(
            content=ft.Container(
                content=ft.Icon(ft.Icons.MORE_VERT, size=16, color=c.TEXT_PLACEHOLDER),
                width=28, height=28,
                border_radius=8,
                ink=True,
                on_hover=lambda e: (
                    setattr(e.control, 'bgcolor', c.BG_HOVER) if e.data == 'true'
                    else setattr(e.control, 'bgcolor', None),
                    e.control.update() if e.control.page else None,
                ),
            ),
            items=menu_items,
            menu_position=ft.PopupMenuPosition.UNDER,
            elevation=8,
            tooltip="更多操作",
        )

    # ---- 数据刷新 ----
    def _refresh_list(self):
        """根据当前筛选和搜索刷新列表"""
        c = self._colors
        self._mail_items_col.controls.clear()

        # 应用筛选
        self._filtered = []
        for mail in self._mails:
            # 筛选 Tab
            if self._current_filter == "unread" and mail.is_read:
                continue
            # 搜索
            if self._search_keyword:
                kw = self._search_keyword.lower()
                if (kw not in (mail.subject or "").lower()
                    and kw not in (mail.sender or "").lower()
                    and kw not in (mail.body_text or "").lower()):
                    continue
            self._filtered.append(mail)

        # 构建列表项
        for mail in self._filtered:
            self._mail_items_col.controls.append(self._build_mail_item(mail))

        # 空状态
        self._empty_view.visible = (len(self._filtered) == 0)

        self.update()

    # ---- 事件处理 ----
    def _on_filter_click(self, e: ft.ControlEvent):
        key = e.control.data
        if not key or key == self._current_filter:
            return
        self._current_filter = key
        # 重建筛选 Tab
        idx = self.controls.index(self._filter_tabs_row)
        self._filter_tabs_row = self._build_filter_tabs()
        self.controls[idx] = self._filter_tabs_row
        self._refresh_list()
        logger.info(f"筛选切换: {key}")

    def _on_search_change(self, e: ft.ControlEvent):
        self._search_keyword = e.control.value or ""
        self._refresh_list()

    def _on_mail_click(self, e: ft.ControlEvent):
        message_id = e.control.data
        if not message_id:
            return
        self._selected_id = message_id
        self._refresh_list()
        if self._on_select:
            self._on_select(message_id)

    def _on_fetch_click(self, e):
        if self._fetching:
            return
        if self._on_fetch:
            self._on_fetch(e)

    # ---- 菜单操作内部处理 ----
    def _mark_read_internal(self, message_id: str):
        """本地标记为已读 + 触发外部回调"""
        for mail in self._mails:
            if mail.message_id == message_id:
                mail.is_read = True
                break
        self._refresh_list()
        if self._cb_mark_read:
            self._cb_mark_read(message_id)

    def _on_mark_read(self, message_id: str):
        """菜单项：标记已读（外部回调 + 本地同步）"""
        self._mark_read_internal(message_id)
        logger.info(f"标记已读: {message_id}")

    def _on_mark_unread(self, message_id: str):
        """菜单项：标记未读"""
        for mail in self._mails:
            if mail.message_id == message_id:
                mail.is_read = False
                break
        self._refresh_list()
        if self._cb_mark_unread:
            self._cb_mark_unread(message_id)
        logger.info(f"标记未读: {message_id}")

    def _on_star_toggle(self, message_id: str):
        """菜单项：加星标 / 取消星标"""
        for mail in self._mails:
            if mail.message_id == message_id:
                tags = list(mail.tags or [])
                if "星标" in tags or mail.priority == "high":
                    if "星标" in tags:
                        tags.remove("星标")
                    mail.tags = tags
                    mail.priority = "normal"
                else:
                    tags.append("星标")
                    mail.tags = tags
                    mail.priority = "high"
                break
        self._refresh_list()
        if self._cb_star:
            self._cb_star(message_id)
        logger.info(f"星标切换: {message_id}")

    def _on_delete(self, message_id: str):
        """菜单项：删除邮件"""
        self._mails = [m for m in self._mails if m.message_id != message_id]
        if self._selected_id == message_id:
            self._selected_id = None
        self._refresh_list()
        if self._cb_delete:
            self._cb_delete(message_id)
        logger.info(f"删除邮件: {message_id}")

    def _on_reply(self, message_id: str):
        """菜单项：回复"""
        if self._cb_reply:
            self._cb_reply(message_id)
        logger.info(f"回复邮件: {message_id}")

    def _on_forward(self, message_id: str):
        """菜单项：转发"""
        if self._cb_forward:
            self._cb_forward(message_id)
        logger.info(f"转发邮件: {message_id}")

    def _on_move(self, message_id: str):
        """菜单项：移动到..."""
        if self._cb_move:
            self._cb_move(message_id)
        logger.info(f"移动邮件: {message_id}")

    def _on_export(self, message_id: str):
        """菜单项：导出邮件"""
        if self._cb_export:
            self._cb_export(message_id)
        logger.info(f"导出邮件: {message_id}")

    # ---- 公共方法 ----
    def set_mails(self, mails: list):
        """设置邮件列表"""
        self._mails = list(mails)
        self._refresh_list()

    def set_title(self, title: str):
        """设置列表标题"""
        self._title.value = title
        self.update()

    def set_fetching(self, fetching: bool):
        """设置拉取中状态"""
        self._fetching = fetching
        c = self._colors
        self._fetch_btn.content.controls[1].value = "拉取中..." if fetching else "拉取"
        self.update()

    def mark_as_read(self, message_id: str):
        """标记邮件为已读"""
        for mail in self._mails:
            if mail.message_id == message_id:
                mail.is_read = True
                break
        self._refresh_list()

    def update_theme(self, is_dark: bool):
        """切换主题"""
        self._is_dark = is_dark
        self._build()
        self._refresh_list()
