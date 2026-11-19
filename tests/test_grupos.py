from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.auth.models import Grupo, Usuario


def test_login_sincroniza_grupo_local(client, auth):
    client.get("/auth/me", headers=auth("ADMIN", "pessoa@teste.gov.br"))

    with SessionLocal() as db:
        usuario = db.scalar(select(Usuario).where(Usuario.email == "pessoa@teste.gov.br"))
        assert [g.nome for g in usuario.grupos] == ["ADMIN"]
        assert db.scalar(select(Grupo).where(Grupo.nome == "ADMIN")) is not None


def test_login_com_novo_papel_atualiza_grupos_do_usuario(client, auth):
    # mesmo e-mail: o segundo login troca o papel do mesmo usuário local
    client.get("/auth/me", headers=auth("EDITOR_TECNICO", "pessoa@teste.gov.br"))
    client.get("/auth/me", headers=auth("GESTOR_INFO", "pessoa@teste.gov.br"))

    with SessionLocal() as db:
        usuario = db.scalar(select(Usuario).where(Usuario.email == "pessoa@teste.gov.br"))
        assert [g.nome for g in usuario.grupos] == ["GESTOR_INFO"]


def test_grupo_e_reaproveitado_entre_usuarios(client, auth):
    client.get("/auth/me", headers=auth("ADMIN", "um@teste.gov.br"))
    client.get("/auth/me", headers=auth("ADMIN", "dois@teste.gov.br"))

    with SessionLocal() as db:
        total = len(db.scalars(select(Grupo).where(Grupo.nome == "ADMIN")).all())
        assert total == 1
