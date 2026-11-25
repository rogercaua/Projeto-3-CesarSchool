from app.modules.auth import oauth2_m2m


def _cliente(escopos=("relatorios:exportar",), client_id="export-job"):
    return oauth2_m2m.ClientM2M(client_id=client_id, escopos=frozenset(escopos))


def test_exportar_m2m_sem_token_e_recusado(client):
    assert client.post("/relatorios/exportar-m2m").status_code == 401


def test_exportar_m2m_token_invalido_e_recusado(client, monkeypatch):
    def _falhar(token):
        raise oauth2_m2m.TokenM2MInvalido("Token inválido ou expirado")

    monkeypatch.setattr(oauth2_m2m, "validar", _falhar)
    r = client.post("/relatorios/exportar-m2m", headers={"Authorization": "Bearer qualquer"})
    assert r.status_code == 401


def test_exportar_m2m_sem_o_escopo_exigido_e_recusado(client, monkeypatch):
    monkeypatch.setattr(oauth2_m2m, "validar", lambda token: _cliente(escopos=()))
    r = client.post("/relatorios/exportar-m2m", headers={"Authorization": "Bearer token"})
    assert r.status_code == 403


def test_exportar_m2m_com_escopo_exporta_para_o_s3(client, monkeypatch, s3):
    monkeypatch.setattr(oauth2_m2m, "validar", lambda token: _cliente())
    r = client.post("/relatorios/exportar-m2m", headers={"Authorization": "Bearer token"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["bucket"] == "bucket-teste"
    assert len(s3.put_object_chamadas) == 1


def test_exportar_m2m_registra_auditoria_com_o_client_id(client, auth, monkeypatch, s3):
    monkeypatch.setattr(oauth2_m2m, "validar", lambda token: _cliente(client_id="job-relatorios"))
    r = client.post("/relatorios/exportar-m2m", headers={"Authorization": "Bearer token"})
    assert r.status_code == 200

    eventos = client.get("/auditoria", headers=auth("ADMIN")).json()["itens"]
    assert eventos[0]["acao"] == "RELATORIO_EXPORTADO_M2M"
    assert eventos[0]["usuario_id"] is None
    assert eventos[0]["detalhes"]["client_id"] == "job-relatorios"
