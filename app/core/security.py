"""Criação (modo dev) e validação (dev/Keycloak) de tokens JWT."""
import time

import jwt
from jwt import PyJWKClient

from app.core.config import settings

_ALGORITMO_DEV = "HS256"
_jwks: PyJWKClient | None = None


def criar_token_dev(sub: str, email: str, nome: str, papeis: list[str]) -> str:
    agora = int(time.time())
    claims = {
        "sub": sub,
        "email": email,
        "name": nome,
        "realm_access": {"roles": papeis},  # mesmo formato do Keycloak
        "iat": agora,
        "exp": agora + settings.jwt_ttl_minutes * 60,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=_ALGORITMO_DEV)


def decodificar_token(token: str) -> dict:
    """Levanta jwt.PyJWTError se o token for inválido."""
    global _jwks
    if settings.auth_mode == "dev":
        return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITMO_DEV])

    if _jwks is None:
        _jwks = PyJWKClient(f"{settings.keycloak_issuer}/protocol/openid-connect/certs")
    chave = _jwks.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        chave.key,
        algorithms=["RS256"],
        issuer=settings.keycloak_issuer,
        audience=settings.keycloak_audience or None,
        options={"verify_aud": bool(settings.keycloak_audience)},
    )
