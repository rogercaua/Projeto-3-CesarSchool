from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import criar_token_local
from app.modules.auditoria.service import registrar
from app.modules.auth import ldap_client
from app.modules.auth.deps import Principal, usuario_atual
from app.modules.auth.models import Usuario
from app.modules.auth.schemas import PAPEIS_VALIDOS, DevLoginIn, LdapLoginIn, TokenOut, UsuarioOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config")
def config():
    """Pública: diz ao front como entrar (login simulado, LDAP ou SSO do Keycloak)."""
    if settings.auth_mode == "dev":
        return {"modo": "dev"}
    if settings.auth_mode == "ldap":
        return {"modo": "ldap"}
    return {"modo": "keycloak", "issuer": settings.keycloak_issuer, "client_id": settings.keycloak_client_id}


@router.post("/dev-login", response_model=TokenOut)
def dev_login(dados: DevLoginIn):
    """Login simulado, só existe com AUTH_MODE=dev."""
    if settings.auth_mode != "dev":
        raise HTTPException(404)
    token = criar_token_local(f"dev:{dados.email}", dados.email, dados.nome, [dados.papel.value])
    return TokenOut(access_token=token)


def _auditar_login(db: Session, request: Request, acao: str, username: str, motivo: str | None = None) -> None:
    """Grava a tentativa de login na trilha (sucesso ou falha), sem a senha.
    O usuário local pode ainda não existir: ele é criado no primeiro acesso autenticado."""
    usuario_id = db.scalar(select(Usuario.id).where(Usuario.keycloak_id == f"ldap:{username}"))
    detalhes = {"usuario": username, "ip": request.client.host if request.client else None}
    if motivo:
        detalhes["motivo"] = motivo
    registrar(db, usuario_id, acao, "sessao", None, detalhes)
    db.commit()


@router.post("/ldap-login", response_model=TokenOut)
def ldap_login(dados: LdapLoginIn, request: Request, db: Session = Depends(get_db)):
    """Bind contra o servidor LDAP; os papéis vêm da interseção dos grupos do
    usuário com o enum Papel. Só existe com AUTH_MODE=ldap."""
    if settings.auth_mode != "ldap":
        raise HTTPException(404)
    try:
        usuario = ldap_client.autenticar(dados.usuario, dados.senha)
    except ldap_client.CredenciaisInvalidas:
        _auditar_login(db, request, "LOGIN_FALHOU", dados.usuario, "credenciais inválidas")
        raise HTTPException(401, "Usuário ou senha inválidos")
    papeis = [g for g in usuario.grupos if g in PAPEIS_VALIDOS]
    if not papeis:
        _auditar_login(db, request, "LOGIN_FALHOU", usuario.username, "sem papel válido")
        raise HTTPException(403, "Usuário sem papel válido no sistema")
    token = criar_token_local(f"ldap:{usuario.username}", usuario.email, usuario.nome, papeis)
    _auditar_login(db, request, "LOGIN", usuario.username)
    return TokenOut(access_token=token)


@router.get("/me", response_model=UsuarioOut)
def me(principal: Principal = Depends(usuario_atual)):
    return UsuarioOut(
        id=principal.id,
        nome=principal.usuario.nome,
        email=principal.usuario.email,
        papeis=sorted(principal.papeis),
    )
