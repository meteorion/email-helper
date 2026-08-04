"""调度配置页面（占位）"""
import flet as ft

def create_schedule_page(page: ft.Page) -> ft.Control:
    """调度配置页面占位"""
    return ft.Container(
        content=ft.Column([
            ft.Text("调度配置", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("Alpha GUI 开发中...", size=14, color=ft.colors.GREY),
        ]),
        padding=30,
    )
