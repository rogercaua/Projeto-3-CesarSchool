"""Exportação de relatório via OIDC Authorization Code + PKCE (delegação de usuário).

Diferente do M2M (`oauth2_m2m.py`): ali um client de serviço troca credenciais por um
token sem usuário por trás; aqui é uma pessoa que loga no Authorization Server e
autoriza a exportação — o ID token devolvido identifica quem autorizou o quê. Modela
o cenário do enunciado (ex.: exportar para o Google Drive) usando o mesmo Authorization
Server já usado para o SSO deste projeto (Keycloak) no lugar do Google.

O estado entre as duas chamadas do fluxo (redirecionar -> voltar com o code) viaja num
cookie assinado (JWT HS256, chave local, expira em poucos minutos) com o `state` e o
`code_verifier` do PKCE — sem precisar de sessão/servidor de estado.
"""
import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

from app.core.config import settings

_ALGORITMO_ESTADO = "HS256"
_TTL_ESTADO_SEGUNDOS = 300
_jwks: PyJWKClient | None = None


class OidcExportError(Exception):
    """Configuração ausente, state inválido/expirado ou ID token recusado."""


@dataclass(frozen=True)
class IdentidadeExportacao:
    sub: str
    username: str
    email: str | None


def _issuer() -> str:
    """Emissor público: usado na URL de login (navegador) e validado no `iss` do ID token."""
    return settings.oidc_export_issuer or settings.keycloak_issuer


def _issuer_interno() -> str:
    """Base usada pelas chamadas da própria API ao Authorization Server (token/JWKS)."""
    return settings.oidc_export_issuer_interno or _issuer()


def _gerar_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def iniciar_autorizacao() -> tuple[str, str]:
    """Monta a URL de login no Authorization Server e o cookie de estado assinado.

    Retorna (url_autorizacao, cookie_estado).
    """
    issuer = _issuer()
    if not (issuer and settings.oidc_export_client_id and settings.oidc_export_redirect_uri):
        raise OidcExportError(
            "OIDC_EXPORT_ISSUER/OIDC_EXPORT_CLIENT_ID/OIDC_EXPORT_REDIRECT_URI não configurados"
        )

    verifier, challenge = _gerar_pkce()
    state = secrets.token_urlsafe(24)
    agora = int(time.time())
    cookie_estado = jwt.encode(
        {"state": state, "code_verifier": verifier, "iat": agora, "exp": agora + _TTL_ESTADO_SEGUNDOS},
        settings.jwt_secret,
        algorithm=_ALGORITMO_ESTADO,
    )
    params = {
        "response_type": "code",
        "client_id": settings.oidc_export_client_id,
        "redirect_uri": settings.oidc_export_redirect_uri,
        "scope": "openid profile email",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = f"{issuer}/protocol/openid-connect/auth?{urlencode(params)}"
    return url, cookie_estado


def concluir_autorizacao(code: str, state: str, cookie_estado: str | None) -> IdentidadeExportacao:
    """Troca o code pelo ID token, valida (assinatura, emissor, state anti-CSRF) e
    devolve a identidade de quem autorizou a exportação."""
    global _jwks
    issuer = _issuer()
    if not cookie_estado:
        raise OidcExportError("Estado da autorização ausente ou expirado")
    try:
        claims_estado = jwt.decode(cookie_estado, settings.jwt_secret, algorithms=[_ALGORITMO_ESTADO])
    except jwt.PyJWTError as erro:
        raise OidcExportError("Estado da autorização inválido ou expirado") from erro
    if not secrets.compare_digest(claims_estado.get("state", ""), state):
        raise OidcExportError("State não confere (possível CSRF)")

    try:
        resposta = httpx.post(
            f"{_issuer_interno()}/protocol/openid-connect/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.oidc_export_redirect_uri,
                "client_id": settings.oidc_export_client_id,
                "code_verifier": claims_estado["code_verifier"],
            },
            timeout=10,
        )
        resposta.raise_for_status()
    except httpx.HTTPError as erro:
        raise OidcExportError(f"Falha ao trocar o código de autorização: {erro}") from erro

    id_token = resposta.json().get("id_token")
    if not id_token:
        raise OidcExportError("Authorization Server não devolveu id_token")

    if _jwks is None:
        _jwks = PyJWKClient(f"{_issuer_interno()}/protocol/openid-connect/certs")
    try:
        chave = _jwks.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token, chave.key, algorithms=["RS256"], issuer=issuer, audience=settings.oidc_export_client_id
        )
    except jwt.PyJWTError as erro:
        raise OidcExportError("ID token inválido ou expirado") from erro

    return IdentidadeExportacao(
        sub=claims["sub"],
        username=claims.get("preferred_username", claims["sub"]),
        email=claims.get("email"),
    )
