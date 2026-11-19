"""Criação (modo dev/ldap, local) e validação (dev/ldap/Keycloak) de tokens JWT."""
import time

import jwt
from jwt import PyJWKClient

from app.core.config import settings

_ALGORITMO_LOCAL = "HS256"
_jwks: PyJWKClient | None = None


def criar_token_local(sub: str, email: str, nome: str, papeis: list[str]) -> str:
    """Token assinado com a chave local (HS256): usado pelo login simulado (dev) e pelo login LDAP."""
    agora = int(time.time())
    claims = {
        "sub": sub,
        "email": email,
        "name": nome,
        "realm_access": {"roles": papeis},  # mesmo formato do Keycloak
        "iat": agora,
        "exp": agora + settings.jwt_ttl_minutes * 60,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=_ALGORITMO_LOCAL)


def decodificar_token(token: str) -> dict:
    """Levanta jwt.PyJWTError se o token for inválido."""
    global _jwks
    if settings.auth_mode in ("dev", "ldap"):
        return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITMO_LOCAL])

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
