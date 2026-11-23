"""Controles de Segurança e Auditoria: login auditado, anonimização (LGPD) e backup."""
import sqlite3

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backup import fazer_backup
from app.core.config import settings
from app.core.database import engine
from app.modules.auditoria.models import AuditoriaEvento
from app.modules.auth import ldap_client
from app.modules.auth.ldap_client import CredenciaisInvalidas, UsuarioLdap


def _eventos_de_sessao():
    with Session(engine) as db:
        return [(e.acao, e.detalhes) for e in db.scalars(
            select(AuditoriaEvento).where(AuditoriaEvento.entidade == "sessao").order_by(AuditoriaEvento.id))]


def test_login_ldap_sucesso_e_falha_vao_para_a_auditoria(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "ldap")

    def autenticar(usuario, senha):
        if senha != "certa":
            raise CredenciaisInvalidas("x")
        return UsuarioLdap(username=usuario, nome="Ana", email="ana@x.gov.br", grupos=["LEITOR"])

    monkeypatch.setattr(ldap_client, "autenticar", autenticar)
    assert client.post("/auth/ldap-login", json={"usuario": "ana", "senha": "errada"}).status_code == 401
    assert client.post("/auth/ldap-login", json={"usuario": "ana", "senha": "certa"}).status_code == 200

    eventos = _eventos_de_sessao()
    assert [a for a, _ in eventos] == ["LOGIN_FALHOU", "LOGIN"]
    assert eventos[0][1]["usuario"] == "ana" and eventos[0][1]["motivo"] == "credenciais inválidas"
    assert all("senha" not in d and "certa" not in str(d) for _, d in eventos)


def test_anonimizacao_apaga_dados_pessoais_e_mantem_historico(client, auth, criar_unidade):
    criar_unidade()  # o editor passa a ter solicitação, então não pode ser excluído
    admin = auth("ADMIN")
    editor = next(u for u in client.get("/usuarios", headers=admin).json() if u["email"] == "editor_tecnico@teste.gov.br")
    assert client.delete(f"/usuarios/{editor['id']}", headers=admin).status_code == 409

    r = client.post(f"/usuarios/{editor['id']}/anonimizacao", headers=admin)
    assert r.status_code == 200
    assert "editor_tecnico" not in str(r.json())
    assert client.post(f"/usuarios/{editor['id']}/anonimizacao", headers=admin).status_code == 409
    assert client.get("/solicitacoes", headers=auth("GESTOR_INFO")).json()["total"] == 1

    eventos = client.get("/auditoria", headers=admin, params={"entidade": "usuario"}).json()["itens"]
    assert eventos[0]["acao"] == "USUARIO_ANONIMIZADO" and eventos[0]["detalhes"] is None

    # o mesmo e-mail volta a entrar como um usuário novo, sem ligação com o anonimizado
    novo = client.get("/auth/me", headers=auth("EDITOR_TECNICO")).json()
    assert novo["id"] != editor["id"]


def test_admin_nao_anonimiza_a_si_mesmo(client, auth):
    admin = auth("ADMIN")
    meu_id = client.get("/auth/me", headers=admin).json()["id"]
    assert client.post(f"/usuarios/{meu_id}/anonimizacao", headers=admin).status_code == 409


def test_backup_copia_o_banco_e_mantem_os_mais_recentes(tmp_path):
    origem = tmp_path / "origem.db"
    with sqlite3.connect(origem) as c:
        c.execute("CREATE TABLE t (x)")
        c.execute("INSERT INTO t VALUES (42)")
    destino = tmp_path / "backups"
    for i in range(3):
        (destino / f"governanca_2000010{i}_000000.db").parent.mkdir(exist_ok=True)
        (destino / f"governanca_2000010{i}_000000.db").write_bytes(b"")

    arquivo = fazer_backup(str(origem), destino, manter=2)

    with sqlite3.connect(arquivo) as c:
        assert c.execute("SELECT x FROM t").fetchone() == (42,)
    assert sorted(p.name for p in destino.iterdir())[-1] == arquivo.name
    assert len(list(destino.iterdir())) == 2
