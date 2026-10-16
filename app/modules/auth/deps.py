from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decodificar_token
from app.modules.auth.models import Usuario
from app.modules.auth.schemas import Papel
from app.modules.auth.service import sincronizar_usuario

_bearer = HTTPBearer(auto_error=False)
_PAPEIS_VALIDOS = {p.value for p in Papel}


@dataclass(frozen=True)
class Principal:
    usuario: Usuario
    papeis: frozenset[Papel]

    @property
    def id(self) -> int:
        return self.usuario.id

    def tem(self, *papeis: Papel) -> bool:
        return bool(self.papeis & set(papeis))


def usuario_atual(
    credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Principal:
    cabecalho = {"WWW-Authenticate": "Bearer"}
    if credenciais is None:
        raise HTTPException(401, "Token ausente", headers=cabecalho)
    try:
        claims = decodificar_token(credenciais.credentials)
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido ou expirado", headers=cabecalho)

    papeis = frozenset(
        Papel(r) for r in claims.get("realm_access", {}).get("roles", []) if r in _PAPEIS_VALIDOS
    )
    if not papeis:
        raise HTTPException(403, "Usuário sem papel válido no sistema")
    return Principal(sincronizar_usuario(db, claims), papeis)


def exigir(*permitidos: Papel):
    """Dependência que só deixa passar quem tem ao menos um dos papéis informados."""

    def verificar(principal: Principal = Depends(usuario_atual)) -> Principal:
        if not principal.tem(*permitidos):
            raise HTTPException(403, "Seu papel não tem permissão para esta ação")
        return principal

    return verificar
