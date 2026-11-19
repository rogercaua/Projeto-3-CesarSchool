from app.core.config import settings
from app.modules.auth import ldap_client
from app.modules.auth.ldap_client import CredenciaisInvalidas, UsuarioLdap


def _modo_ldap(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "ldap")


def test_ldap_login_inexistente_fora_do_modo_ldap(client):
    assert client.post("/auth/ldap-login", json={"usuario": "x", "senha": "y"}).status_code == 404


def test_config_reporta_modo_ldap(client, monkeypatch):
    _modo_ldap(monkeypatch)
    assert client.get("/auth/config").json() == {"modo": "ldap"}


def test_ldap_login_sucesso_mapeia_grupo_em_papel(client, monkeypatch):
    _modo_ldap(monkeypatch)
    monkeypatch.setattr(
        ldap_client, "autenticar",
        lambda usuario, senha: UsuarioLdap(
            username=usuario, nome="Editor Teste", email="editor.teste@governanca.local",
            grupos=["EDITOR_TECNICO", "GRUPO_SEM_MAPEAMENTO"],
        ),
    )
    r = client.post("/auth/ldap-login", json={"usuario": "editor.teste", "senha": "Senha123!"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["papeis"] == ["EDITOR_TECNICO"]
    assert me.json()["email"] == "editor.teste@governanca.local"


def test_ldap_login_credenciais_invalidas(client, monkeypatch):
    _modo_ldap(monkeypatch)

    def _falhar(usuario, senha):
        raise CredenciaisInvalidas("Usuário ou senha inválidos")

    monkeypatch.setattr(ldap_client, "autenticar", _falhar)
    r = client.post("/auth/ldap-login", json={"usuario": "editor.teste", "senha": "errada"})
    assert r.status_code == 401


def test_ldap_login_sem_grupo_mapeado_e_recusado(client, monkeypatch):
    _modo_ldap(monkeypatch)
    monkeypatch.setattr(
        ldap_client, "autenticar",
        lambda usuario, senha: UsuarioLdap(
            username=usuario, nome="Sem Papel", email="sem.papel@governanca.local", grupos=["OUTRO_GRUPO"],
        ),
    )
    r = client.post("/auth/ldap-login", json={"usuario": "sem.papel", "senha": "Senha123!"})
    assert r.status_code == 403
