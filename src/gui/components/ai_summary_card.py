"""AI 摘要卡片组件（占位）"""
import flet as ft

def create_ai_summary_card(mail_data) -> ft.Control:
    """AI 摘要卡片占位"""
    return ft.Container(
        content=ft.Column([
            ft.Text("AI 智能分类", size=14, weight=ft.FontWeight.BOLD),
            ft.Text("Alpha GUI 开发中...", size=12, color=ft.colors.GREY),
        ]),
        padding=10,
        border=ft.border.all(1, ft.colors.GREY_300),
        border_radius=8,
    )
