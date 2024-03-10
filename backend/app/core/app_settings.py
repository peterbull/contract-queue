import os
from dataclasses import dataclass


class AppSettings:
    # database settings
    postgres_user: str = os.getenv("POSTGRES_USER")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD")
    postgres_port: int = os.getenv("POSTGRES_PORT")
    postgres_db: str = os.getenv("POSTGRES_DB")
    postgres_server: str = os.getenv("POSTGRES_SERVER")
    postgres_db_driver: str = os.getenv("POSTGRES_DB_DRIVER")

    @property
    def database_settings(self):
        return {
            "postgres_user": self.postgres_user,
            "postgres_password": self.postgres_password,
            "postgres_port": self.postgres_port,
            "postgres_db": self.postgres_db,
            "postrgres_server": self.postgres_server,
            "postgres_db_driver": self.postgres_db_driver,
        }

    @property
    def database_conn_string(self):
        return (
            f"postgresql+{self.postgres_db_driver}://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_server}:{self.postgres_port}/{self.postgres_db}"
        )


class AsyncAppSettings:
    # database settings
    postgres_user: str = os.getenv("POSTGRES_USER")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD")
    postgres_port: int = os.getenv("POSTGRES_PORT")
    postgres_db: str = os.getenv("POSTGRES_DB")
    postgres_server: str = os.getenv("POSTGRES_SERVER")
    postgres_db_driver: str = os.getenv("POSTGRES_ASYNC_DB_DRIVER")

    @property
    def database_settings(self):
        return {
            "postgres_user": self.postgres_user,
            "postgres_password": self.postgres_password,
            "postgres_port": self.postgres_port,
            "postgres_db": self.postgres_db,
            "postrgres_server": self.postgres_server,
            "postgres_db_driver": self.postgres_db_driver,
        }

    @property
    def database_conn_string(self):
        return (
            f"postgresql+{self.postgres_db_driver}://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_server}:{self.postgres_port}/{self.postgres_db}"
        )


# Swap for dataclass once fully switched to async
# @dataclass
# class DatabaseConfig:
#     driver: str
#     user: str
#     password: str
#     server: str
#     port: str
#     db: str

#     @property
#     def conn_string(self):
#         return f"postgresql+{self.driver}://{self.user}:{self.password}@{self.server}:{self.port}/{self.db}"
