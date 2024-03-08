import os


class AppSettings:
    # database settings
    postgres_user: str = os.getenv("POSTGRES_USER")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD")
    postgres_port: int = os.getenv("POSTGRES_PORT")
    postgres_db: str = os.getenv("POSTGRES_DB")
    postgres_server: str = os.getenv("POSTGRES_SERVER")

    @property
    def database_settings(self):
        return {
            "postgres_user": self.postgres_user,
            "postgres_password": self.postgres_password,
            "postgres_port": self.postgres_port,
            "postgres_db": self.postgres_db,
            "postrgres_server": self.postgres_server,
        }

    @property
    def database_conn_string(self):
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_server}:{self.postgres_port}/{self.postgres_db}"
        )
