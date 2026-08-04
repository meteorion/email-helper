"""AI 摘要卡片组件（占位）"""
import flet as ft
from src.gui.theme import Color, Radius, Font


def create_ai_summary_card(mail_data) -> ft.Control:
    """AI 摘要卡片占位"""
    return ft.Container(
        content=ft.Column([
            ft.Text("AI 智能分类", size=Font.BODY, weight=ft.FontWeight.W_600),
            ft.Text("Alpha GUI 开发中...", size=Font.AUX, color=Color.TEXT_SECONDARY),
        ]),
        padding=ft.Padding(10, 10, 10, 10),
        border=ft.Border.all(1, Color.BORDER),
        border_radius=Radius.CARD,
    )
