from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import Usuario


def sincronizar_usuario(db: Session, claims: dict) -> Usuario:
    """Cria o usuário local no primeiro acesso e mantém nome/e-mail atualizados."""
    sub = claims["sub"]
    nome = claims.get("name") or claims.get("preferred_username") or sub
    email = claims.get("email") or ""

    usuario = db.scalar(select(Usuario).where(Usuario.keycloak_id == sub))
    if usuario is None:
        usuario = Usuario(keycloak_id=sub, nome=nome, email=email)
        db.add(usuario)
        db.commit()
    elif (usuario.nome, usuario.email) != (nome, email):
        usuario.nome, usuario.email = nome, email
        db.commit()
    return usuario
