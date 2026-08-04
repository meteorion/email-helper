"""分类标签组件（占位）"""
import flet as ft

CATEGORY_COLORS = {
    "审批类": ft.colors.BLUE,
    "通知类": ft.colors.TEAL,
    "会议类": ft.colors.PURPLE,
    "协作类": ft.colors.ORANGE,
    "资讯类": ft.colors.GREY,
    "告警类": ft.colors.RED,
    "营销类": ft.colors.PINK,
    "垃圾邮件": ft.colors.GREY_400,
}

def create_category_badge(category: str | None) -> ft.Control:
    """创建分类标签"""
    if not category:
        return ft.Container(width=0)
    color = CATEGORY_COLORS.get(category, ft.colors.GREY)
    return ft.Container(
        content=ft.Text(category, size=11, color=ft.colors.WHITE),
        bgcolor=color,
        border_radius=4,
        padding=ft.padding.symmetric(horizontal=6, vertical=2),
    )
