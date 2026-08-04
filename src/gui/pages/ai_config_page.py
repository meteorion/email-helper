"""AI 设置页面（占位）"""
import flet as ft

def create_ai_config_page(page: ft.Page) -> ft.Control:
    """AI 设置页面占位"""
    return ft.Container(
        content=ft.Column([
            ft.Text("AI 设置", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("Alpha GUI 开发中...", size=14, color=ft.colors.GREY),
        ]),
        padding=30,
    )
