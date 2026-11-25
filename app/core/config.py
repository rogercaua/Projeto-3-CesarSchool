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
    # "ldap": bind do usuário/senha contra um servidor LDAP (emite token local, igual ao "dev")
    auth_mode: Literal["dev", "keycloak", "ldap"] = "dev"
    jwt_secret: str = "troque-esta-chave"  # usada em modo dev e ldap (tokens locais)
    jwt_ttl_minutes: int = 480
    # Chave AES-256 (32 bytes em base64) das colunas cifradas; gere com:
    # python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
    cripto_chave: str = CRIPTO_CHAVE_DEV
    keycloak_issuer: str = ""  # ex.: https://sso.exemplo.gov.br/realms/saude
    keycloak_audience: str = ""  # opcional
    keycloak_client_id: str = ""  # cliente público do front (login no navegador)
    ldap_url: str = ""  # ex.: ldap://34.233.125.128:389
    ldap_base_dn: str = ""  # ex.: dc=governanca,dc=local
    ldap_user_dn_template: str = "uid={username},ou=people,{base_dn}"
    ldap_group_search_base: str = "ou=groups,{base_dn}"
    # Exportação de relatórios para o S3. Credenciais não ficam aqui: o boto3 já lê
    # AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_SESSION_TOKEN do ambiente sozinho
    # (inclusive as credenciais temporárias do AWS Academy Learner Lab).
    aws_region: str = "us-east-1"
    s3_bucket: str = ""

    # Autorização M2M (OAuth2 client_credentials) para POST /relatorios/exportar-m2m.
    # Reaproveita o mesmo Authorization Server do login SSO: vazio usa KEYCLOAK_ISSUER.
    # Independe de AUTH_MODE (funciona mesmo com dev/ldap para os usuários humanos).
    oauth2_m2m_issuer: str = ""
    # client_id (claim "azp"/"client_id" do token) aceito; vazio aceita qualquer client
    # que tenha o escopo exigido pelo endpoint.
    oauth2_m2m_client_id: str = ""

    @model_validator(mode="after")
    def _checar_keycloak(self):
        if self.auth_mode == "keycloak" and not (self.keycloak_issuer and self.keycloak_client_id):
            raise ValueError("KEYCLOAK_ISSUER e KEYCLOAK_CLIENT_ID são obrigatórios quando AUTH_MODE=keycloak")
        if self.auth_mode == "keycloak" and self.cripto_chave == CRIPTO_CHAVE_DEV:
            raise ValueError("Defina CRIPTO_CHAVE: a chave padrão é pública e só serve para desenvolvimento")
        if self.auth_mode == "ldap" and not (self.ldap_url and self.ldap_base_dn):
            raise ValueError("LDAP_URL e LDAP_BASE_DN são obrigatórios quando AUTH_MODE=ldap")
        return self


settings = Settings()
