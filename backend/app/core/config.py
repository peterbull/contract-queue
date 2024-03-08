"""App configuration functions and access to settings"""
from app.core.app_settings import AppSettings


def get_app_settings() -> AppSettings:
    return AppSettings()
