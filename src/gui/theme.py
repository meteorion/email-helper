"""Flet 主题配置 - 深浅双主题 + 设计规范常量

严格对齐 email_desktop_ui_design.html 设计稿的色值与字号。
配色取自 Tailwind CSS 调色板（blue / slate / gray 系列）。
"""

import flet as ft


# ---------------------------------------------------------------------------
# 设计规范常量（与 email_desktop_ui_design.html 对齐）
# ---------------------------------------------------------------------------

class Color:
    """颜色常量（浅色主题）"""

    # 主色（Tailwind blue 系列）
    PRIMARY_900 = "#1E3A8A"      # Rail 深蓝背景
    PRIMARY_700 = "#2563EB"      # 主色按下 / 链接
    PRIMARY_500 = "#3B82F6"      # 主色 / 未读标记 / 链接
    PRIMARY_400 = "#60A5FA"      # 浅主色 / 选中竖条 / Rail 文字
    PRIMARY_300 = "#93C5FD"      # Rail 未选中文字
    PRIMARY_100 = "#DBEAFE"      # 选中背景
    PRIMARY_50 = "#EFF6FF"       # 未读背景

    # 应用主色（用于按钮、链接）
    PRIMARY = PRIMARY_500
    PRIMARY_HOVER = PRIMARY_700
    PRIMARY_PRESS = "#1D4ED8"
    PRIMARY_CONTAINER = PRIMARY_50

    # 背景
    BG_MAIN = "#FFFFFF"          # 主背景白
    BG_SIDEBAR = "#F8FAFC"       # 侧栏浅灰
    BG_CARD = "#FFFFFF"          # 卡片/面板
    BG_SELECTED = "#DBEAFE"      # 选中行（蓝浅）
    BG_HOVER = "#F8FAFC"         # 悬停行
    BG_RAIL = PRIMARY_900        # 导航 Rail 深蓝
    BG_RAIL_HOVER = "rgba(255,255,255,0.08)"
    BG_RAIL_SELECTED = "rgba(59,130,246,0.30)"
    BG_UNREAD = PRIMARY_50       # 未读邮件背景
    BG_REPLY = "#FAFAFA"         # 回复区背景

    # 文字
    TEXT_PRIMARY = "#111827"     # 主文字（近黑，Gray 900）
    TEXT_SECONDARY = "#6B7280"   # 次要文字（Gray 500）
    TEXT_PLACEHOLDER = "#9CA3AF" # 占位文字（Gray 400）
    TEXT_ON_PRIMARY = "#FFFFFF"
    TEXT_RAIL = PRIMARY_300      # Rail 未选中文字
    TEXT_RAIL_SELECTED = "#FFFFFF"  # Rail 选中文字

    # 分割线/边框
    BORDER = "#E5E7EB"           # Gray 200
    BORDER_LIGHT = "#F3F4F6"     # Gray 100
    BORDER_RAIL = "#1E293B"      # 深色边框

    # 语义色
    SUCCESS = "#10B981"          # Emerald 500
    WARNING = "#F59E0B"          # Amber 500
    ERROR = "#EF4444"            # Red 500
    INFO = "#8B5CF6"             # Violet 500
    IMPORTANT = "#EC4899"        # Pink 500
    STAR = "#F59E0B"             # 星标颜色
    UNREAD = PRIMARY_500

    # 标签色（背景 / 文字）
    TAG_WORK = ("#FEE2E2", "#991B1B")        # 工作 红
    TAG_PROJECT = ("#DBEAFE", "#1E40AF")     # 项目 蓝
    TAG_FINANCE = ("#DCFCE7", "#166534")     # 财务 绿
    TAG_PERSONAL = ("#FEF3C7", "#92400E")    # 个人 黄
    TAG_MEETING = ("#EDE9FE", "#6D28D9")     # 会议 紫
    TAG_IMPORTANT = ("#FCE7F3", "#9F1239")   # 重要 粉
    TAG_HIGH = ("#EDE9FE", "#6D28D9")        # 高优先级 紫

    # 渐变
    LOGO_GRADIENT = [PRIMARY_500, PRIMARY_400]                # Logo 蓝→浅蓝
    COMPOSE_GRADIENT = [PRIMARY_500, PRIMARY_700]             # 撰写按钮 蓝→深蓝
    AVATAR_GRADIENT_1 = ["#F472B6", "#FB923C"]               # 粉→橙
    AVATAR_GRADIENT_2 = ["#6366F1", "#8B5CF6"]               # 靛→紫
    AVATAR_GRADIENT_3 = ["#10B981", "#34D399"]               # 绿→浅绿
    STORAGE_GRADIENT = [SUCCESS, PRIMARY_500]                 # 绿→蓝
    ATTACH_PDF_GRADIENT = ["#FEE2E2", "#FECACA"]             # PDF 红
    ATTACH_XLS_GRADIENT = ["#DBEAFE", "#BFDBFE"]             # Excel 蓝


class DarkColor:
    """颜色常量（深色主题）"""

    # 主色保持不变
    PRIMARY_900 = "#1E3A8A"
    PRIMARY_700 = "#2563EB"
    PRIMARY_500 = "#3B82F6"
    PRIMARY_400 = "#60A5FA"
    PRIMARY_300 = "#93C5FD"
    PRIMARY_100 = "rgba(59,130,246,0.18)"
    PRIMARY_50 = "rgba(59,130,246,0.08)"

    PRIMARY = PRIMARY_400
    PRIMARY_HOVER = PRIMARY_500
    PRIMARY_PRESS = PRIMARY_500
    PRIMARY_CONTAINER = PRIMARY_50

    # 背景
    BG_MAIN = "#0F172A"          # Slate 900
    BG_SIDEBAR = "#0F172A"
    BG_CARD = "#0F172A"
    BG_SELECTED = "rgba(59,130,246,0.18)"
    BG_HOVER = "#1E293B"
    BG_RAIL = "#0C1428"
    BG_RAIL_HOVER = "rgba(255,255,255,0.08)"
    BG_RAIL_SELECTED = "rgba(59,130,246,0.30)"
    BG_UNREAD = PRIMARY_50
    BG_REPLY = "#0F172A"

    # 文字
    TEXT_PRIMARY = "#F1F5F9"     # Slate 100
    TEXT_SECONDARY = "#94A3B8"   # Slate 400
    TEXT_PLACEHOLDER = "#475569"
    TEXT_ON_PRIMARY = "#FFFFFF"
    TEXT_RAIL = PRIMARY_300
    TEXT_RAIL_SELECTED = "#FFFFFF"

    # 边框
    BORDER = "#1E293B"
    BORDER_LIGHT = "#1E293B"
    BORDER_RAIL = "#1E293B"

    # 语义色（深色模式略调亮）
    SUCCESS = "#10B981"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"
    INFO = "#8B5CF6"
    IMPORTANT = "#EC4899"
    STAR = "#F59E0B"
    UNREAD = PRIMARY_500

    # 标签色（深色模式透明度更高）
    TAG_WORK = ("rgba(239,68,68,0.20)", "#FCA5A5")
    TAG_PROJECT = ("rgba(59,130,246,0.20)", "#93C5FD")
    TAG_FINANCE = ("rgba(16,185,129,0.20)", "#6EE7B7")
    TAG_PERSONAL = ("rgba(245,158,11,0.20)", "#FCD34D")
    TAG_MEETING = ("rgba(139,92,246,0.20)", "#C4B5FD")
    TAG_IMPORTANT = ("rgba(236,72,153,0.20)", "#F9A8D4")
    TAG_HIGH = ("rgba(139,92,246,0.20)", "#C4B5FD")

    LOGO_GRADIENT = [PRIMARY_500, PRIMARY_400]
    COMPOSE_GRADIENT = [PRIMARY_500, PRIMARY_700]
    AVATAR_GRADIENT_1 = ["#F472B6", "#FB923C"]
    AVATAR_GRADIENT_2 = ["#6366F1", "#8B5CF6"]
    AVATAR_GRADIENT_3 = ["#10B981", "#34D399"]
    STORAGE_GRADIENT = [SUCCESS, PRIMARY_500]
    ATTACH_PDF_GRADIENT = ["rgba(254,226,226,0.20)", "rgba(254,202,202,0.20)"]
    ATTACH_XLS_GRADIENT = ["rgba(219,234,254,0.20)", "rgba(191,219,254,0.20)"]


# 标签名 → 颜色映射（用于动态匹配）
TAG_COLOR_MAP = {
    "工作": "WORK",
    "项目": "PROJECT",
    "项目 Alpha": "PROJECT",
    "财务": "FINANCE",
    "个人": "PERSONAL",
    "会议": "MEETING",
    "重要": "IMPORTANT",
    "高优先级": "HIGH",
}


class Radius:
    """圆角规范"""
    BUTTON = 6          # 按钮 / 输入框
    CARD = 8             # 卡片 / 面板
    LIST_ITEM = 8        # 列表项（设计稿用 8px）
    DIALOG = 12          # 对话框
    PILL = 999           # 胶囊（撰写按钮 / 徽章 / 头像）
    ROUND = 50           # 圆形百分比（用 width/2）
    CHIP = 14            # 收件人 chip
    TAB = 4              # 复选框


class Font:
    """字号层级"""
    WINDOW_TITLE = 16   # Bold（窗口标题）
    PANEL_TITLE = 18    # Semibold（面板标题，列表头）
    DETAIL_SUBJECT = 24 # Bold（邮件详情大标题）
    BODY_LG = 15        # Semibold（发件人名）
    BODY = 14           # Regular（正文/邮件主题）
    BODY_SM = 13        # Regular（次要正文/按钮/标签）
    AUX = 12            # Regular（辅助文字/时间/状态栏）
    SMALL = 11          # 小徽章/附件大小
    TINY = 10           # 邮件标签


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
            on_primary_container=color.PRIMARY_700,
            secondary=color.PRIMARY,
            surface=color.BG_CARD,
            surface_container_low=color.BG_SIDEBAR,
            surface_container=color.BG_HOVER,
            error=color.ERROR,
            on_error=color.TEXT_ON_PRIMARY,
            outline=color.BORDER,
            outline_variant=color.BORDER_LIGHT,
            on_surface=color.TEXT_PRIMARY,
            on_surface_variant=color.TEXT_SECONDARY,
        ),
        font_family="-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    )


# 浅色 / 深色主题
LIGHT_THEME = _build_theme(Color)
DARK_THEME = _build_theme(DarkColor)

# 向后兼容：APP_THEME 指向浅色主题
APP_THEME = LIGHT_THEME
