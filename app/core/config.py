from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Aceita qualquer URL do SQLAlchemy: sqlite, postgresql+psycopg2, mysql+pymysql...
    database_url: str = "sqlite:///./governanca.db"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5500", "http://127.0.0.1:5500"]

    # "dev": login simulado (equivale ao "simular perfil" do protótipo)
    # "keycloak": valida tokens RS256 emitidos pelo Keycloak
    auth_mode: Literal["dev", "keycloak"] = "dev"
    jwt_secret: str = "troque-esta-chave"  # só usada em modo dev
    jwt_ttl_minutes: int = 480
    keycloak_issuer: str = ""  # ex.: https://sso.exemplo.gov.br/realms/saude
    keycloak_audience: str = ""  # opcional

    @model_validator(mode="after")
    def _checar_keycloak(self):
        if self.auth_mode == "keycloak" and not self.keycloak_issuer:
            raise ValueError("KEYCLOAK_ISSUER é obrigatório quando AUTH_MODE=keycloak")
        return self


settings = Settings()
