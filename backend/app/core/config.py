"""App configuration functions and access to settings"""

from app.core.app_settings import AppSettings, AsyncAppSettings


def get_app_settings() -> AppSettings:
    return AppSettings()


def get_async_app_settings() -> AsyncAppSettings:
    return AsyncAppSettings()
