from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Batalha de Farejador"
    database_url: str = f"sqlite:///{(Path(__file__).resolve().parents[3] / 'farejador.db').as_posix()}"
    jwt_secret: str = "CHANGE_ME_TO_A_LONG_RANDOM_SECRET"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175"
    cookie_secure: bool = False
    trust_proxy_headers: bool = False
    ipinfo_timeout_seconds: int = 4
    admin_email: str = "admin@farejador.local"
    admin_password: str = "ChangeThisPassword123!"
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")
    @property
    def cors_list(self): return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

@lru_cache
def get_settings(): return Settings()
