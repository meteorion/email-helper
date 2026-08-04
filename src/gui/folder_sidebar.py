"""文件夹侧栏组件 - Flet 实现（第二栏 260px）

严格对齐 email_desktop_ui_design.html 设计稿：
  - 顶部：撰写邮件胶囊按钮（蓝色渐变）
  - 文件夹分组：常用 + 管理（带图标 + 未读徽章）
  - 标签区：彩色圆点标签
  - 底部：存储进度条
"""

import flet as ft

from src.gui.theme import Color, DarkColor, Radius, Font
from src.core.logger import get_logger

logger = get_logger("gui.folder_sidebar")


# 文件夹定义：(key, 名称, 图标, 默认未读数, 是否灰徽章)
DEFAULT_FOLDERS = [
    ("inbox", "收件箱", ft.Icons.INBOX_OUTLINED, 0, False),
    ("sent", "已发送", ft.Icons.SEND_OUTLINED, 0, False),
    ("drafts", "草稿箱", ft.Icons.DRAFTS_OUTLINED, 0, True),
    ("starred", "星标邮件", ft.Icons.STAR_OUTLINE, 0, True),
    ("important", "重要", ft.Icons.LABEL_OUTLINED, 0, False),
]

MANAGE_FOLDERS = [
    ("attachments", "带附件", ft.Icons.ATTACHMENT_OUTLINED, 0, True),
    ("trash", "已删除", ft.Icons.DELETE_OUTLINE, 0, False),
    ("spam", "垃圾箱", ft.Icons.REPORT_OUTLINED, 0, False),
]

# 标签定义：(key, 名称, 圆点颜色属性名)
LABELS = [
    ("work", "工作", "TAG_WORK"),
    ("project", "项目 Alpha", "TAG_PROJECT"),
    ("finance", "财务", "TAG_FINANCE"),
    ("personal", "个人", "TAG_PERSONAL"),
    ("meeting", "会议", "TAG_MEETING"),
]


@ft.control("Column", init=False)
class FolderSidebar(ft.Column):
    """文件夹侧栏视图"""

    def __init__(self, on_select=None, on_compose=None, is_dark: bool = False):
        super().__init__()
        self.spacing = 0
        self.expand = True
        self._on_select = on_select
        self._on_compose = on_compose
        self._is_dark = is_dark
        self._selected = "inbox"
        self._folder_items: dict[str, ft.Container] = {}
        self._count_badges: dict[str, ft.Container] = {}
        self._counts: dict[str, int] = {}

        self._build()

    # ---- 颜色辅助 ----
    @property
    def _colors(self):
        return DarkColor if self._is_dark else Color

    # ---- 构建 UI ----
    def _build(self):
        c = self._colors
        self.controls = [
            # 1. 撰写邮件按钮
            self._build_compose_btn(),
            # 2. 常用文件夹分组
            self._build_section_title("常用"),
            self._build_folder_list(DEFAULT_FOLDERS),
            # 3. 管理文件夹分组
            self._build_section_title("管理"),
            self._build_folder_list(MANAGE_FOLDERS),
            # 4. 标签区
            self._build_section_title("标签"),
            self._build_labels(),
            # 5. 弹性占位
            ft.Container(expand=True),
            # 6. 底部存储进度
            self._build_storage_info(),
        ]

    def _build_compose_btn(self) -> ft.Container:
        """撰写邮件按钮（蓝色渐变胶囊，外层 16px padding）"""
        c = self._colors
        btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.EDIT_OUTLINED, size=16, color=c.TEXT_ON_PRIMARY),
                    ft.Text(
                        "撰写邮件",
                        size=Font.BODY_SM,
                        color=c.TEXT_ON_PRIMARY,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
            on_click=self._on_compose_click,
            padding=ft.Padding(16, 9, 16, 9),
            border_radius=Radius.PILL,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0),
                end=ft.Alignment(1, 0),
                colors=c.COMPOSE_GRADIENT,
            ),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color="rgba(59,130,246,0.30)",
                offset=ft.Offset(0, 2),
            ),
            ink=True,
        )
        # 外层 wrap（设计稿 .compose-btn-wrap padding 16px）
        return ft.Container(content=btn, padding=ft.Padding(16, 16, 16, 16))

    def _build_section_title(self, title: str) -> ft.Container:
        """分组小标题（11px 大写灰色）"""
        c = self._colors
        return ft.Container(
            content=ft.Text(
                title,
                size=11,
                weight=ft.FontWeight.W_600,
                color=c.TEXT_PLACEHOLDER,
                # 设计稿 letter-spacing 0.5px
            ),
            padding=ft.Padding(20, 16, 12, 8),
        )

    def _build_folder_list(self, folders: list) -> ft.Container:
        """文件夹列表容器"""
        col = ft.Column(spacing=2, expand=False)
        for key, name, icon, count, is_gray in folders:
            col.controls.append(self._build_folder_item(key, name, icon, count, is_gray))
        return ft.Container(
            content=col,
            padding=ft.Padding(12, 0, 12, 0),
        )

    def _build_folder_item(self, key: str, name: str, icon: str,
                            count: int, is_gray: bool) -> ft.Container:
        """单个文件夹项（图标 + 名称 + 徽章）"""
        c = self._colors
        is_selected = (key == self._selected)

        # 图标
        icon_color = c.PRIMARY_700 if is_selected else c.TEXT_SECONDARY
        icon_ctrl = ft.Icon(icon, size=18, color=icon_color)

        # 名称
        name_weight = ft.FontWeight.W_600 if is_selected else ft.FontWeight.W_400
        name_color = c.PRIMARY_700 if is_selected else c.TEXT_PRIMARY
        name_ctrl = ft.Text(
            name,
            size=Font.BODY,
            color=name_color,
            weight=name_weight,
            expand=True,
        )

        # 未读徽章
        badge_bg = c.BORDER if is_gray else c.PRIMARY_500
        badge_text_color = c.TEXT_SECONDARY if is_gray else c.TEXT_ON_PRIMARY
        badge_text = ft.Text(
            str(count) if count > 0 else "",
            size=Font.SMALL,
            color=badge_text_color,
            weight=ft.FontWeight.W_600,
        )
        badge = ft.Container(
            content=badge_text,
            bgcolor=badge_bg,
            border_radius=Radius.PILL,
            padding=ft.Padding(8, 2, 8, 2),
            visible=(count > 0),
            alignment=ft.Alignment(0, 0),
        )
        self._count_badges[key] = badge

        item = ft.Container(
            content=ft.Row(
                [icon_ctrl, name_ctrl, badge],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                spacing=10,
            ),
            data=key,
            on_click=self._on_folder_click,
            padding=ft.Padding(12, 10, 12, 10),
            border_radius=Radius.LIST_ITEM,
            bgcolor=c.BG_SELECTED if is_selected else None,
            ink=True,
        )
        self._folder_items[key] = item
        return item

    def _build_labels(self) -> ft.Container:
        """标签区"""
        c = self._colors
        col = ft.Column(spacing=2)
        for key, name, color_attr in LABELS:
            bg_color, _text_color = getattr(c, color_attr)
            col.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                width=10,
                                height=10,
                                border_radius=3,
                                bgcolor=bg_color,
                            ),
                            ft.Text(
                                name,
                                size=Font.BODY_SM,
                                color=c.TEXT_PRIMARY,
                            ),
                        ],
                        spacing=10,
                    ),
                    data=key,
                    on_click=self._on_label_click,
                    padding=ft.Padding(12, 8, 12, 8),
                    border_radius=Radius.LIST_ITEM,
                    ink=True,
                )
            )

        # 新建标签
        col.controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            width=10,
                            height=10,
                            border_radius=3,
                            bgcolor=c.BORDER,
                            border=ft.Border.all(1, c.TEXT_PLACEHOLDER),
                        ),
                        ft.Text(
                            "新建标签",
                            size=Font.BODY_SM,
                            color=c.TEXT_SECONDARY,
                        ),
                    ],
                    spacing=10,
                ),
                padding=ft.Padding(12, 8, 12, 8),
                border_radius=Radius.LIST_ITEM,
                ink=True,
            )
        )

        return ft.Container(
            content=col,
            padding=ft.Padding(12, 0, 12, 0),
        )

    def _build_storage_info(self) -> ft.Container:
        """底部存储进度条"""
        c = self._colors
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "存储空间",
                        size=Font.BODY_SM,
                        weight=ft.FontWeight.W_500,
                        color=c.TEXT_PRIMARY,
                    ),
                    # 进度条
                    ft.Container(
                        content=ft.Stack(
                            [
                                # 背景
                                ft.Container(
                                    width=210,
                                    height=6,
                                    bgcolor=c.BORDER,
                                    border_radius=3,
                                ),
                                # 填充（68%）
                                ft.Container(
                                    width=210 * 0.68,
                                    height=6,
                                    border_radius=3,
                                    gradient=ft.LinearGradient(
                                        begin=ft.Alignment(-1, 0),
                                        end=ft.Alignment(1, 0),
                                        colors=c.STORAGE_GRADIENT,
                                    ),
                                ),
                            ],
                        ),
                        margin=ft.Margin(0, 8, 0, 8),
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                "6.8 GB / 10 GB 已使用",
                                size=Font.AUX,
                                color=c.TEXT_SECONDARY,
                                expand=True,
                            ),
                            ft.Text(
                                "升级空间 →",
                                size=Font.SMALL,
                                color=c.PRIMARY_700,
                            ),
                        ],
                        spacing=4,
                    ),
                ],
                spacing=0,
            ),
            padding=ft.Padding(16, 16, 16, 16),
            border=ft.Border(top=ft.border.BorderSide(1, c.BORDER)),
        )

    # ---- 事件处理 ----
    def _on_folder_click(self, e: ft.ControlEvent):
        key = e.control.data
        if not key:
            return
        self._select(key)

    def _on_label_click(self, e: ft.ControlEvent):
        key = e.control.data
        if not key:
            return
        self._select(key)

    def _on_compose_click(self, e: ft.ControlEvent):
        if self._on_compose:
            self._on_compose(e)

    def _select(self, key: str):
        self._clear_selection()
        self._selected = key
        self._refresh_styles()
        logger.info(f"选中: {key}")
        if self._on_select:
            self._on_select(key)
        self.update()

    def _clear_selection(self):
        for item in self._folder_items.values():
            item.bgcolor = None

    def _refresh_styles(self):
        c = self._colors
        for key, item in self._folder_items.items():
            if key == self._selected:
                item.bgcolor = c.BG_SELECTED
            else:
                item.bgcolor = None

    # ---- 公共方法 ----
    def select(self, key: str):
        """选中某个文件夹"""
        self._select(key)

    def update_theme(self, is_dark: bool):
        """切换主题时刷新配色"""
        self._is_dark = is_dark
        self._build()
        self.update()

    def set_unread_count(self, folder_key: str, count: int):
        """设置文件夹未读数"""
        self._counts[folder_key] = count
        if folder_key not in self._count_badges:
            return
        badge = self._count_badges[folder_key]
        if count > 0:
            badge.content.value = str(count)
            badge.visible = True
        else:
            badge.visible = False
        self.update()
