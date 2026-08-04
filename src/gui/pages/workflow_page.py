"""流程管理页面（占位）"""
import flet as ft

def create_workflow_page(page: ft.Page) -> ft.Control:
    """流程管理页面占位"""
    return ft.Container(
        content=ft.Column([
            ft.Text("流程管理", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("Alpha GUI 开发中...", size=14, color=ft.colors.GREY),
        ]),
        padding=30,
    )
