from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import agora, engine


def test_triggers_registram_historico_de_status(client, auth, criar_unidade):
    criar_unidade()  # inclusão PENDENTE -> APROVADA
    h = client.get("/banco/historico-status", headers=auth("GESTOR_INFO")).json()
    assert [(x["status_anterior"], x["status_novo"]) for x in reversed(h)] == [(None, "PENDENTE"), ("PENDENTE", "APROVADA")]
    assert h[0]["protocolo"].startswith("SOL-")


def test_trigger_bloqueia_cnes_invalido_e_auditoria_imutavel(client, criar_unidade):
    uid = criar_unidade()
    with engine.begin() as c, pytest.raises(IntegrityError, match="7 dígitos"):
        c.execute(text("UPDATE unidades SET codigo_cnes = '12' WHERE id = :id"), {"id": uid})
    with engine.begin() as c, pytest.raises(IntegrityError, match="imutáveis"):
        c.execute(text("DELETE FROM auditoria_eventos"))


def test_views_com_filtros(client, auth, criar_unidade):
    criar_unidade()
    h = auth("GESTOR_INFO")
    r = client.get("/banco/views/vw_unidades_por_distrito", headers=h).json()
    linha = dict(zip(r["colunas"], r["linhas"][0]))
    assert linha["total_unidades"] == 1 and linha["pct_com_cnes"] == 100.0

    r = client.get("/banco/views/vw_solicitacoes_detalhadas?status=APROVADA", headers=h).json()
    assert len(r["linhas"]) == 1 and r["linhas"][0][r["colunas"].index("gestor")] == "Gestor_Info"
    assert client.get("/banco/views/vw_solicitacoes_detalhadas?status=REJEITADA", headers=h).json()["linhas"] == []
    assert client.get("/banco/views/sqlite_master", headers=h).status_code == 404


def test_funcoes_sql(client, auth):
    h = auth("GESTOR_INFO")
    assert client.post("/banco/funcoes/fn_percentual", headers=h, json={"argumentos": [1, 4]}).json() == {"resultado": 25.0}
    r = client.post("/banco/funcoes/fn_dias_entre", headers=h, json={"argumentos": ["2026-01-01", "2026-01-11"]})
    assert r.json() == {"resultado": 10.0}
    assert client.post("/banco/funcoes/fn_nao_existe", headers=h, json={"argumentos": []}).status_code == 404


def test_procedimento_cancela_paradas_e_dispara_trigger(client, auth, distrito_id):
    r = client.post("/solicitacoes", headers=auth("EDITOR_TECNICO"), json={
        "tipo": "INCLUSAO", "justificativa": "Teste",
        "dados_propostos": {"nome": "UBS Parada", "tipo": "UBS", "distrito_id": distrito_id},
    })
    sid = r.json()["id"]
    with engine.begin() as c:  # envelhece a solicitação em 40 dias
        c.execute(text("UPDATE solicitacoes SET atualizada_em = :d WHERE id = :id"),
                  {"d": (agora() - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S.%f"), "id": sid})

    assert client.post("/banco/procedimentos/sp_cancelar_paradas", headers=auth("GESTOR_INFO"),
                       json={"dias": 30}).status_code == 403
    r = client.post("/banco/procedimentos/sp_cancelar_paradas", headers=auth("ADMIN"), json={"dias": 30})
    assert r.json() == {"canceladas": 1, "ids": [sid]}
    assert client.get(f"/solicitacoes/{sid}", headers=auth("GESTOR_INFO")).json()["status"] == "CANCELADA"
    h = client.get("/banco/historico-status", headers=auth("GESTOR_INFO")).json()
    assert h[0]["status_novo"] == "CANCELADA"


def test_dashboard_estatisticas(client, auth, criar_unidade):
    criar_unidade()
    r = client.get("/dashboard/estatisticas", headers=auth("LEITOR"))
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["indicadores"]["solicitacoes"] == 1 and corpo["indicadores"]["taxa_aprovacao"] == 100.0
    assert corpo["por_status"] == [{"chave": "APROVADA", "total": 1}]
    assert corpo["gestores"][0]["aprovadas"] == 1
    assert client.get("/dashboard/estatisticas?inicio=2026-05-01&fim=2026-01-01", headers=auth("LEITOR")).status_code == 422


def test_crud_usuarios(client, auth):
    h = auth("ADMIN")
    r = client.post("/usuarios", headers=h, json={"nome": "Ana", "email": "ana@recife.gov.br"})
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    assert client.post("/usuarios", headers=h, json={"nome": "Outra", "email": "ANA@recife.gov.br"}).status_code == 409
    assert client.put(f"/usuarios/{uid}", headers=h, json={"nome": "Ana Lima", "email": "ana@recife.gov.br"}).json()["nome"] == "Ana Lima"
    assert any(u["id"] == uid for u in client.get("/usuarios?q=lima", headers=h).json())
    assert client.get("/usuarios", headers=auth("GESTOR_INFO")).status_code == 403
    assert client.delete(f"/usuarios/{uid}", headers=h).status_code == 204
    admin_id = client.get("/auth/me", headers=h).json()["id"]
    assert client.delete(f"/usuarios/{admin_id}", headers=h).status_code == 409
