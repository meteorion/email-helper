"""Flet Material 3 主题配置"""

import flet as ft


APP_THEME = ft.Theme(
    color_scheme=ft.ColorScheme(
        primary=ft.Colors.BLUE_600,
        on_primary=ft.Colors.WHITE,
        primary_container=ft.Colors.BLUE_50,
        on_primary_container=ft.Colors.BLUE_900,
        secondary=ft.Colors.BLUE_400,
        surface=ft.Colors.WHITE,
        surface_container_low=ft.Colors.GREY_50,
        surface_container=ft.Colors.GREY_100,
        error=ft.Colors.RED_600,
        on_error=ft.Colors.WHITE,
        outline=ft.Colors.GREY_300,
        outline_variant=ft.Colors.GREY_200,
        on_surface=ft.Colors.GREY_900,
        on_surface_variant=ft.Colors.GREY_600,
    ),
    use_material3=True,
    font_family="Microsoft YaHei",
)