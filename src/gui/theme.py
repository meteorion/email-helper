"""Flet 主题配置 - 深浅双主题 + 设计规范常量

设计风格：简洁、清新、呼吸感、克制
参考：Notion / Fluent Design / macOS Mail
配色遵循 docs/mvp-tasks.md 9.1 节规范
"""

import flet as ft


# ---------------------------------------------------------------------------
# 设计规范常量（与 email_desktop_ui_design.html 对齐）
# ---------------------------------------------------------------------------

class Color:
    """颜色常量（浅色主题）"""

    # 背景
    BG_MAIN = "#F7F8FA"          # 主背景（极浅灰蓝）
    BG_SIDEBAR = "#FFFFFF"       # 侧栏背景
    BG_CARD = "#FFFFFF"          # 卡片/面板
    BG_SELECTED = "#EEF4FF"      # 选中行
    BG_HOVER = "#F2F5FA"         # 悬停行
    BG_RAIL = "#FFFFFF"          # 导航 Rail

    # 主色
    PRIMARY = "#4A90D9"          # 清爽蓝
    PRIMARY_HOVER = "#3A7BC8"
    PRIMARY_PRESS = "#2E6AB5"
    PRIMARY_CONTAINER = "#EEF4FF"

    # 文字
    TEXT_PRIMARY = "#1D2129"     # 主文字（近黑）
    TEXT_SECONDARY = "#86909C"   # 次要文字
    TEXT_PLACEHOLDER = "#C9CDD4" # 占位文字
    TEXT_ON_PRIMARY = "#FFFFFF"

    # 分割线/边框
    BORDER = "#E5E6EB"
    BORDER_LIGHT = "#F2F3F5"

    # 语义色
    SUCCESS = "#00B42A"
    WARNING = "#FF7D00"
    ERROR = "#F53F3F"
    UNREAD = "#4A90D9"           # 未读标记蓝


class DarkColor:
    """颜色常量（深色主题）"""

    BG_MAIN = "#0F172A"
    BG_SIDEBAR = "#1E293B"
    BG_CARD = "#1E293B"
    BG_SELECTED = "#1E3A5F"
    BG_HOVER = "#27364A"
    BG_RAIL = "#1E293B"

    PRIMARY = "#60A5FA"
    PRIMARY_HOVER = "#7CB7F5"
    PRIMARY_PRESS = "#4A90D9"
    PRIMARY_CONTAINER = "#1E3A5F"

    TEXT_PRIMARY = "#F1F5F9"
    TEXT_SECONDARY = "#94A3B8"
    TEXT_PLACEHOLDER = "#475569"
    TEXT_ON_PRIMARY = "#FFFFFF"

    BORDER = "#334155"
    BORDER_LIGHT = "#27364A"

    SUCCESS = "#22C55E"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"
    UNREAD = "#60A5FA"


class Radius:
    """圆角规范（4px 基准）"""
    BUTTON = 6          # 按钮 / 输入框
    CARD = 8            # 卡片 / 面板
    LIST_ITEM = 4       # 列表项
    DIALOG = 12         # 对话框
    PILL = 999          # 胶囊（标签 / 小徽章）


class Font:
    """字号层级"""
    WINDOW_TITLE = 16   # Bold
    PANEL_TITLE = 14    # Medium
    BODY = 13           # Regular（正文/邮件主题）
    AUX = 12            # Regular（辅助文字/时间/状态栏）
    SMALL = 11          # 小徽章


# ---------------------------------------------------------------------------
# 主题构建
# ---------------------------------------------------------------------------

def _build_theme(color: type) -> ft.Theme:
    """根据颜色类构建 Flet Theme"""
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=color.PRIMARY,
            on_primary=color.TEXT_ON_PRIMARY,
            primary_container=color.PRIMARY_CONTAINER,
            on_primary_container=color.PRIMARY,
            secondary=color.PRIMARY,
            surface=color.BG_CARD,
            surface_container_low=color.BG_MAIN,
            surface_container=color.BG_HOVER,
            error=color.ERROR,
            on_error=color.TEXT_ON_PRIMARY,
            outline=color.BORDER,
            outline_variant=color.BORDER_LIGHT,
            on_surface=color.TEXT_PRIMARY,
            on_surface_variant=color.TEXT_SECONDARY,
        ),
        font_family="Microsoft YaHei UI",
    )


# 浅色 / 深色主题
LIGHT_THEME = _build_theme(Color)
DARK_THEME = _build_theme(DarkColor)

# 向后兼容：APP_THEME 指向浅色主题
APP_THEME = LIGHT_THEME
