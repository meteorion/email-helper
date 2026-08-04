"""写邮件对话框（占位）"""
import flet as ft

class ComposeDialog:
    """写邮件对话框占位"""
    def __init__(self, page: ft.Page, smtp_client=None):
        self.page = page
        self.smtp_client = smtp_client
        self._dialog = ft.AlertDialog(
            title=ft.Text("写邮件"),
            content=ft.Text("Alpha GUI 开发中...", color=ft.colors.GREY),
        )

    def show(self):
        self.page.open(self._dialog)

    def get_compose_data(self) -> dict | None:
        return None
