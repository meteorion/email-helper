"""分类标签组件（占位）"""
import flet as ft
from src.gui.theme import Color, Radius, Font

CATEGORY_COLORS = {
    "审批类": Color.PRIMARY_500,
    "通知类": Color.SUCCESS,
    "会议类": Color.INFO,
    "协作类": Color.WARNING,
    "资讯类": Color.TEXT_SECONDARY,
    "告警类": Color.ERROR,
    "营销类": Color.IMPORTANT,
    "垃圾邮件": Color.TEXT_PLACEHOLDER,
}


def create_category_badge(category: str | None) -> ft.Control:
    """创建分类标签"""
    if not category:
        return ft.Container(width=0)
    color = CATEGORY_COLORS.get(category, Color.TEXT_SECONDARY)
    return ft.Container(
        content=ft.Text(category, size=Font.SMALL, color=Color.TEXT_ON_PRIMARY),
        bgcolor=color,
        border_radius=Radius.TAB,
        padding=ft.Padding(6, 2, 6, 2),
    )
