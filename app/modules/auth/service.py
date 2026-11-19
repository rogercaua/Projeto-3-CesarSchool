from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import Grupo, Usuario
from app.modules.auth.schemas import Papel


def _grupo(db: Session, nome: str) -> Grupo:
    grupo = db.scalar(select(Grupo).where(Grupo.nome == nome))
    if grupo is None:
        grupo = Grupo(nome=nome)
        db.add(grupo)
        db.flush()
    return grupo


def sincronizar_usuario(db: Session, claims: dict, papeis: frozenset[Papel]) -> Usuario:
    """Cria o usuário local no primeiro acesso, mantém nome/e-mail atualizados e
    espelha nas tabelas locais (Grupo/usuario_grupo) os papéis vindos do IdP
    nesse login — tanto para Keycloak/OIDC quanto para LDAP."""
    sub = claims["sub"]
    nome = claims.get("name") or claims.get("preferred_username") or sub
    email = claims.get("email") or ""

    usuario = db.scalar(select(Usuario).where(Usuario.keycloak_id == sub))
    if usuario is None:
        usuario = Usuario(keycloak_id=sub, nome=nome, email=email)
        db.add(usuario)
    elif (usuario.nome, usuario.email) != (nome, email):
        usuario.nome, usuario.email = nome, email

    usuario.grupos = [_grupo(db, p.value) for p in sorted(papeis)]
    db.commit()
    return usuario
