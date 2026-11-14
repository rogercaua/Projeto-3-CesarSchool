from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


CRIPTO_CHAVE_DEV = "ZGV2LXNvbWVudGUtdHJvcXVlLWVzdGEtY2hhdmUtMzI="  # pública: só para desenvolvimento


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
    # Chave AES-256 (32 bytes em base64) das colunas cifradas; gere com:
    # python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
    cripto_chave: str = CRIPTO_CHAVE_DEV
    keycloak_issuer: str = ""  # ex.: https://sso.exemplo.gov.br/realms/saude
    keycloak_audience: str = ""  # opcional
    keycloak_client_id: str = ""  # cliente público do front (login no navegador)

    @model_validator(mode="after")
    def _checar_keycloak(self):
        if self.auth_mode == "keycloak" and not (self.keycloak_issuer and self.keycloak_client_id):
            raise ValueError("KEYCLOAK_ISSUER e KEYCLOAK_CLIENT_ID são obrigatórios quando AUTH_MODE=keycloak")
        if self.auth_mode == "keycloak" and self.cripto_chave == CRIPTO_CHAVE_DEV:
            raise ValueError("Defina CRIPTO_CHAVE: a chave padrão é pública e só serve para desenvolvimento")
        return self


settings = Settings()
