"""Validação de access tokens OAuth2 Client Credentials (M2M).

Modelo Machine-to-Machine: um client de serviço (sem usuário por trás) troca
client_id + client_secret por um access_token direto no Authorization Server
(grant_type=client_credentials) e chama esta API com esse token. Essa troca
acontece inteiramente fora desta aplicação; aqui só validamos o token recebido:
assinatura (JWKS do Authorization Server), emissor, client autorizado (opcional)
e o escopo exigido pelo endpoint.
"""
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

from app.core.config import settings


class TokenM2MInvalido(Exception):
    """Token ausente, malformado, de emissor/client errado ou expirado."""


@dataclass(frozen=True)
class ClientM2M:
    client_id: str
    escopos: frozenset[str]

    def tem_escopo(self, escopo: str) -> bool:
        return escopo in self.escopos


_jwks: PyJWKClient | None = None


def _issuer() -> str:
    return settings.oauth2_m2m_issuer or settings.keycloak_issuer


def validar(token: str) -> ClientM2M:
    """Decodifica e valida o access_token (RS256) do Authorization Server.

    Levanta TokenM2MInvalido se a assinatura, o emissor ou o client não conferirem.
    """
    global _jwks
    issuer = _issuer()
    if not issuer:
        raise TokenM2MInvalido("OAUTH2_M2M_ISSUER/KEYCLOAK_ISSUER não configurado")

    if _jwks is None:
        _jwks = PyJWKClient(f"{issuer}/protocol/openid-connect/certs")
    try:
        chave = _jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(token, chave.key, algorithms=["RS256"], issuer=issuer, options={"verify_aud": False})
    except jwt.PyJWTError as erro:
        raise TokenM2MInvalido("Token inválido ou expirado") from erro

    client_id = claims.get("azp") or claims.get("client_id") or ""
    if settings.oauth2_m2m_client_id and client_id != settings.oauth2_m2m_client_id:
        raise TokenM2MInvalido("Client não autorizado para operações M2M")

    escopos = frozenset((claims.get("scope") or "").split())
    return ClientM2M(client_id=client_id, escopos=escopos)
