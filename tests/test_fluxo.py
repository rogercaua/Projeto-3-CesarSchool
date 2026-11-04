import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.modules.auditoria.models import AuditoriaEvento


def pedir_alteracao(client, headers, unidade_id, **dados):
    return client.post("/solicitacoes", headers=headers, json={
        "tipo": "ALTERACAO", "unidade_id": unidade_id,
        "dados_propostos": dados, "justificativa": "Correção cadastral",
    })


def decidir(client, headers, solicitacao_id, resultado="APROVADA", justificativa="Conferido"):
    return client.post(f"/solicitacoes/{solicitacao_id}/decisao", headers=headers,
                       json={"resultado": resultado, "justificativa": justificativa})


def test_inclusao_aprovada_cria_unidade(client, auth, criar_unidade):
    unidade_id = criar_unidade()
    u = client.get(f"/unidades/{unidade_id}", headers=auth("LEITOR")).json()
    assert u["nome"] == "UBS Centro" and u["codigo"] == "U001" and u["status"] == "ATIVO"


def test_aprovacao_altera_cadastro_e_guarda_versao_anterior(client, auth, criar_unidade):
    uid = criar_unidade()
    r = pedir_alteracao(client, auth("EDITOR_TECNICO"), uid, nome="UBS Nova", qtd_servicos=9)
    assert r.status_code == 201
    s = r.json()
    assert s["status"] == "PENDENTE" and s["protocolo"].startswith("SOL-")
    assert s["dados_atuais"] == {"nome": "UBS Centro", "qtd_servicos": 4}

    d = decidir(client, auth("GESTOR_INFO"), s["id"])
    assert d.status_code == 200
    corpo = d.json()
    assert corpo["status"] == "APROVADA"
    assert corpo["decisoes"][0]["snapshot_anterior"]["nome"] == "UBS Centro"
    assert corpo["decisoes"][0]["gestor_nome"] == "Gestor_Info"
    assert corpo["unidade_cnes"] == "2077604"

    u = client.get(f"/unidades/{uid}", headers=auth("LEITOR")).json()
    assert (u["nome"], u["qtd_servicos"]) == ("UBS Nova", 9)

    eventos = client.get("/auditoria", headers=auth("ADMIN")).json()["itens"]
    assert eventos[0]["usuario_nome"] == "Gestor_Info"
    acoes = {e["acao"] for e in eventos}
    assert {"SOLICITACAO_CRIADA", "SOLICITACAO_APROVADA"} <= acoes


def test_inativacao(client, auth, criar_unidade):
    uid = criar_unidade()
    r = client.post("/solicitacoes", headers=auth("EDITOR_TECNICO"),
                    json={"tipo": "INATIVACAO", "unidade_id": uid, "justificativa": "Unidade fechada"})
    decidir(client, auth("GESTOR_INFO"), r.json()["id"])
    assert client.get(f"/unidades/{uid}", headers=auth("LEITOR")).json()["status"] == "INATIVO"
    assert client.get("/dashboard/resumo", headers=auth("LEITOR")).json()["unidades_ativas"] == 0


def pedir_mudanca_de_status(client, headers, tipo, unidade_id):
    return client.post("/solicitacoes", headers=headers,
                       json={"tipo": tipo, "unidade_id": unidade_id, "justificativa": "Mudança de situação"})


def test_reativacao(client, auth, criar_unidade):
    uid = criar_unidade()
    editor, gestor = auth("EDITOR_TECNICO"), auth("GESTOR_INFO")
    decidir(client, gestor, pedir_mudanca_de_status(client, editor, "INATIVACAO", uid).json()["id"])

    r = client.post("/solicitacoes", headers=editor, json={
        "tipo": "REATIVACAO", "unidade_id": uid, "justificativa": "Unidade reaberta",
        "dados_propostos": {"nome": "Ignorado na reativação"},
    })
    assert r.status_code == 201
    s = r.json()
    assert s["dados_atuais"] == {"status": "INATIVO"} and s["dados_propostos"] is None
    # enquanto não é aprovada, a unidade continua inativa
    assert client.get(f"/unidades/{uid}", headers=editor).json()["status"] == "INATIVO"

    d = decidir(client, gestor, s["id"])
    assert d.status_code == 200
    assert d.json()["decisoes"][0]["snapshot_anterior"]["status"] == "INATIVO"

    u = client.get(f"/unidades/{uid}", headers=editor).json()
    assert u["status"] == "ATIVO" and u["nome"] == "UBS Centro"
    assert client.get("/dashboard/resumo", headers=editor).json()["unidades_ativas"] == 1

    acoes = {e["acao"] for e in client.get("/auditoria", headers=auth("ADMIN")).json()["itens"]}
    assert "SOLICITACAO_APROVADA" in acoes


def test_reativacao_recusada_em_unidade_ativa(client, auth, criar_unidade):
    uid = criar_unidade()
    editor, gestor = auth("EDITOR_TECNICO"), auth("GESTOR_INFO")
    assert pedir_mudanca_de_status(client, editor, "REATIVACAO", uid).status_code == 409
    assert pedir_mudanca_de_status(client, editor, "REATIVACAO", 999).status_code == 404

    decidir(client, gestor, pedir_mudanca_de_status(client, editor, "INATIVACAO", uid).json()["id"])
    # dois pedidos em aberto: o segundo fica sem efeito depois que o primeiro é aprovado
    primeiro = pedir_mudanca_de_status(client, editor, "REATIVACAO", uid).json()["id"]
    segundo = pedir_mudanca_de_status(client, editor, "REATIVACAO", uid).json()["id"]
    assert decidir(client, gestor, primeiro).status_code == 200
    assert decidir(client, gestor, segundo).status_code == 409


def test_reativacao_devolvida_e_reenviada(client, auth, criar_unidade):
    uid = criar_unidade()
    editor, gestor = auth("EDITOR_TECNICO"), auth("GESTOR_INFO")
    decidir(client, gestor, pedir_mudanca_de_status(client, editor, "INATIVACAO", uid).json()["id"])

    sid = pedir_mudanca_de_status(client, editor, "REATIVACAO", uid).json()["id"]
    assert decidir(client, gestor, sid, "DEVOLVIDA", "Falta o comprovante").status_code == 200
    r = client.put(f"/solicitacoes/{sid}", headers=editor,
                   json={"dados_propostos": {"nome": "Ignorado"}, "justificativa": "Comprovante anexado"})
    assert r.status_code == 200 and r.json()["status"] == "PENDENTE" and r.json()["dados_propostos"] is None
    assert decidir(client, gestor, sid).status_code == 200
    assert client.get(f"/unidades/{uid}", headers=editor).json()["status"] == "ATIVO"


def test_reativacao_exige_papel_de_editor(client, auth, criar_unidade):
    uid = criar_unidade()
    for papel in ("LEITOR", "GESTOR_INFO", "ADMIN"):
        assert pedir_mudanca_de_status(client, auth(papel), "REATIVACAO", uid).status_code == 403


def cancelar(client, headers, solicitacao_id, justificativa="Aberta por engano"):
    return client.post(f"/solicitacoes/{solicitacao_id}/cancelamento", headers=headers,
                       json={"justificativa": justificativa})


def test_cancelar_pendente_e_devolvida(client, auth, criar_unidade):
    uid = criar_unidade()
    editor, gestor = auth("EDITOR_TECNICO"), auth("GESTOR_INFO")

    pendente = pedir_alteracao(client, editor, uid, nome="Outro nome").json()["id"]
    r = cancelar(client, editor, pendente)
    assert r.status_code == 200 and r.json()["status"] == "CANCELADA"

    devolvida = pedir_alteracao(client, editor, uid, nome="Outro nome").json()["id"]
    decidir(client, gestor, devolvida, "DEVOLVIDA", "Falta comprovante")
    assert cancelar(client, editor, devolvida).json()["status"] == "CANCELADA"

    assert client.get(f"/unidades/{uid}", headers=editor).json()["nome"] == "UBS Centro"
    assert client.get("/solicitacoes/contagem", headers=gestor).json()["CANCELADA"] == 2
    assert client.get("/solicitacoes", headers=gestor, params={"status": "CANCELADA"}).json()["total"] == 2

    eventos = client.get("/auditoria", headers=auth("ADMIN")).json()["itens"]
    assert eventos[0]["acao"] == "SOLICITACAO_CANCELADA"
    assert eventos[0]["detalhes"]["justificativa"] == "Aberta por engano"


def test_cancelada_fica_encerrada(client, auth, criar_unidade):
    uid = criar_unidade()
    editor, gestor = auth("EDITOR_TECNICO"), auth("GESTOR_INFO")
    sid = pedir_alteracao(client, editor, uid, nome="Outro nome").json()["id"]
    cancelar(client, editor, sid)

    assert cancelar(client, editor, sid).status_code == 409
    assert decidir(client, gestor, sid).status_code == 409
    assert client.put(f"/solicitacoes/{sid}", headers=editor, json={"justificativa": "Reabrir"}).status_code == 409


def test_nao_cancela_solicitacao_ja_decidida(client, auth, criar_unidade):
    uid = criar_unidade()
    editor, gestor = auth("EDITOR_TECNICO"), auth("GESTOR_INFO")
    aprovada = pedir_alteracao(client, editor, uid, nome="Nome A").json()["id"]
    rejeitada = pedir_alteracao(client, editor, uid, nome="Nome B").json()["id"]
    decidir(client, gestor, aprovada)
    decidir(client, gestor, rejeitada, "REJEITADA", "Sem amparo")

    assert cancelar(client, editor, aprovada).status_code == 409
    assert cancelar(client, editor, rejeitada).status_code == 409


def test_so_o_solicitante_cancela(client, auth, criar_unidade):
    uid = criar_unidade()
    editor = auth("EDITOR_TECNICO")
    sid = pedir_alteracao(client, editor, uid, nome="Outro nome").json()["id"]

    assert cancelar(client, auth("EDITOR_TECNICO", "outro@teste.gov.br"), sid).status_code == 403
    for papel in ("LEITOR", "GESTOR_INFO", "ADMIN"):
        assert cancelar(client, auth(papel), sid).status_code == 403
    assert cancelar(client, editor, 999).status_code == 404
    assert cancelar(client, editor, sid, justificativa="ok").status_code == 422
    assert client.get(f"/solicitacoes/{sid}", headers=editor).json()["status"] == "PENDENTE"


def test_justificativa_obrigatoria_na_decisao(client, auth, criar_unidade):
    uid = criar_unidade()
    sid = pedir_alteracao(client, auth("EDITOR_TECNICO"), uid, nome="Outro nome").json()["id"]
    gestor = auth("GESTOR_INFO")
    assert client.post(f"/solicitacoes/{sid}/decisao", headers=gestor, json={"resultado": "APROVADA"}).status_code == 422
    assert decidir(client, gestor, sid, justificativa="ok").status_code == 422


def test_devolver_reenviar_e_rejeitar(client, auth, criar_unidade):
    uid = criar_unidade()
    editor, gestor = auth("EDITOR_TECNICO"), auth("GESTOR_INFO")
    sid = pedir_alteracao(client, editor, uid, nome="Nome errado").json()["id"]

    assert decidir(client, gestor, sid, "DEVOLVIDA", "Falta comprovante").json()["status"] == "DEVOLVIDA"
    r = client.put(f"/solicitacoes/{sid}", headers=editor, json={"dados_propostos": {"nome": "Nome certo"}})
    assert r.status_code == 200 and r.json()["status"] == "PENDENTE"
    assert r.json()["dados_propostos"] == {"nome": "Nome certo"}

    assert decidir(client, gestor, sid, "REJEITADA", "Sem amparo").json()["status"] == "REJEITADA"
    assert client.get(f"/unidades/{uid}", headers=editor).json()["nome"] == "UBS Centro"
    assert decidir(client, gestor, sid).status_code == 409  # já decidida

    contagem = client.get("/solicitacoes/contagem", headers=gestor).json()
    assert contagem["REJEITADA"] == 1 and contagem["TODOS"] == 2  # inclusão aprovada + esta


def test_permissoes_por_papel(client, auth, criar_unidade):
    uid = criar_unidade()
    assert client.get("/unidades").status_code == 401
    assert pedir_alteracao(client, auth("LEITOR"), uid, nome="X1").status_code == 403
    assert client.get("/solicitacoes", headers=auth("LEITOR")).status_code == 403
    assert client.get("/auditoria", headers=auth("GESTOR_INFO")).status_code == 403

    sid = pedir_alteracao(client, auth("EDITOR_TECNICO"), uid, nome="Novo nome").json()["id"]
    assert decidir(client, auth("EDITOR_TECNICO", "outro@teste.gov.br"), sid).status_code == 403
    # editor só enxerga as próprias solicitações
    outro = auth("EDITOR_TECNICO", "outro@teste.gov.br")
    assert client.get("/solicitacoes", headers=outro).json()["total"] == 0
    assert client.get(f"/solicitacoes/{sid}", headers=outro).status_code == 403
    assert client.get("/solicitacoes", headers=auth("GESTOR_INFO")).json()["total"] == 2


def test_separacao_de_funcoes(client, auth, criar_unidade):
    uid = criar_unidade()
    # mesmo e-mail = mesmo usuário, mesmo com tokens de papéis diferentes
    editor = auth("EDITOR_TECNICO", "pessoa@teste.gov.br")
    gestor = auth("GESTOR_INFO", "pessoa@teste.gov.br")
    sid = pedir_alteracao(client, editor, uid, nome="Nome B").json()["id"]
    assert decidir(client, gestor, sid).status_code == 403


def test_cnes_duplicado_e_validacoes(client, auth, criar_unidade):
    criar_unidade("UBS A", "2077604")
    uid_b = criar_unidade("UBS B", "9848271")
    editor = auth("EDITOR_TECNICO")
    assert pedir_alteracao(client, editor, uid_b, codigo_cnes="2077604").status_code == 409
    assert pedir_alteracao(client, editor, uid_b, codigo_cnes="12").status_code == 422
    assert pedir_alteracao(client, editor, uid_b, nome=None).status_code == 422
    assert pedir_alteracao(client, editor, uid_b).status_code == 422  # nada a alterar
    assert pedir_alteracao(client, editor, 999, nome="Fantasma").status_code == 404


def test_cnes_busca_e_conciliacao(client, auth, criar_unidade):
    criar_unidade("UBS Centro", "2077604")  # no CNES simulado o nome é "UBS Vila Madalena"
    gestor = auth("GESTOR_INFO")
    assert client.get("/cnes/estabelecimentos/2077604", headers=gestor).json()["nome"] == "UBS Vila Madalena"
    assert client.get("/cnes/estabelecimentos/0000000", headers=gestor).status_code == 404

    div = client.get("/cnes/conciliacao", headers=gestor).json()
    assert any(d["divergencia"] == "CAMPO_DIVERGENTE" and d["campo"] == "nome" for d in div)
    assert client.get("/cnes/conciliacao", headers=auth("LEITOR")).status_code == 403


def test_filtros_de_unidades(client, auth, criar_unidade):
    criar_unidade("UBS Centro", "2077604")
    criar_unidade("AMA Norte", None)
    leitor = auth("LEITOR")
    assert client.get("/unidades?q=norte", headers=leitor).json()["total"] == 1
    assert client.get("/unidades?q=U001", headers=leitor).json()["itens"][0]["nome"] == "UBS Centro"
    assert client.get("/unidades?sem_cnes=true", headers=leitor).json()["total"] == 1
    assert client.get("/dashboard/resumo", headers=leitor).json()["sem_codigo_cnes"] == 1


def test_auditoria_e_imutavel(client, auth, criar_unidade):
    criar_unidade()
    with Session(engine) as db:
        evento = db.query(AuditoriaEvento).first()
        evento.acao = "ADULTERADO"
        with pytest.raises(RuntimeError):
            db.commit()
        db.rollback()
        db.delete(evento)
        with pytest.raises(RuntimeError):
            db.commit()
