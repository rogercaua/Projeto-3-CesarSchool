from app.core.config import settings
from app.modules.auth import oidc_export


def _configurar(monkeypatch):
    monkeypatch.setattr(settings, "oidc_export_issuer", "http://keycloak-teste/realms/saude")
    monkeypatch.setattr(settings, "oidc_export_client_id", "govcadastral-oidc-export")
    monkeypatch.setattr(settings, "oidc_export_redirect_uri", "http://testserver/relatorios/oidc/callback")


def test_iniciar_sem_configuracao_e_erro_de_servidor(client):
    r = client.get("/relatorios/exportar-oidc/iniciar", follow_redirects=False)
    assert r.status_code == 500


def test_iniciar_redireciona_para_o_authorization_server_com_pkce(client, monkeypatch):
    _configurar(monkeypatch)
    r = client.get("/relatorios/exportar-oidc/iniciar", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"].startswith("http://keycloak-teste/realms/saude/protocol/openid-connect/auth?")
    assert "code_challenge=" in r.headers["location"]
    assert "code_challenge_method=S256" in r.headers["location"]
    assert r.cookies.get("oidc_export_estado")


def test_callback_sem_cookie_de_estado_e_recusado(client, monkeypatch):
    _configurar(monkeypatch)
    r = client.get("/relatorios/oidc/callback", params={"code": "abc", "state": "xyz"})
    assert r.status_code == 401


def test_callback_com_state_divergente_e_recusado(client, monkeypatch):
    _configurar(monkeypatch)
    inicio = client.get("/relatorios/exportar-oidc/iniciar", follow_redirects=False)
    r = client.get("/relatorios/oidc/callback", params={"code": "abc", "state": "state-errado"})
    assert r.status_code == 401


def test_callback_com_id_token_valido_exporta_para_o_s3_com_usuario(client, monkeypatch, s3):
    _configurar(monkeypatch)
    inicio = client.get("/relatorios/exportar-oidc/iniciar", follow_redirects=False)
    location = inicio.headers["location"]
    state = dict(p.split("=", 1) for p in location.split("?", 1)[1].split("&"))["state"]

    monkeypatch.setattr(
        oidc_export,
        "concluir_autorizacao",
        lambda code, state_recebido, cookie: oidc_export.IdentidadeExportacao(
            sub="abc123", username="gestor.teste", email="gestor.teste@governanca.local"
        ),
    )
    r = client.get("/relatorios/oidc/callback", params={"code": "codigo-valido", "state": state})
    assert r.status_code == 200
    corpo = r.json()
    assert "oidc/gestor.teste" in corpo["chave"]
    assert len(s3.put_object_chamadas) == 1


def test_callback_registra_auditoria_com_o_usuario_oidc(client, monkeypatch, auth, s3):
    _configurar(monkeypatch)
    monkeypatch.setattr(
        oidc_export,
        "concluir_autorizacao",
        lambda code, state, cookie: oidc_export.IdentidadeExportacao(
            sub="abc123", username="gestor.teste", email=None
        ),
    )
    r = client.get("/relatorios/oidc/callback", params={"code": "codigo-valido", "state": "qualquer"})
    assert r.status_code == 200

    eventos = client.get("/auditoria", headers=auth("ADMIN")).json()["itens"]
    assert eventos[0]["acao"] == "RELATORIO_EXPORTADO_OIDC"
    assert eventos[0]["usuario_id"] is None
    assert eventos[0]["detalhes"]["usuario_oidc"] == "gestor.teste"
