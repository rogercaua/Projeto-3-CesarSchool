def acoes_de_distrito(client, auth):
    eventos = client.get("/auditoria", headers=auth("ADMIN"), params={"entidade": "distrito"}).json()["itens"]
    return [e["acao"] for e in eventos]


def test_criar_remove_espacos_e_recusa_invalidos(client, auth):
    admin = auth("ADMIN")
    r = client.post("/distritos", headers=admin, json={"nome": "  Distrito Norte  "})
    assert r.status_code == 201 and r.json()["nome"] == "Distrito Norte"
    assert client.post("/distritos", headers=admin, json={"nome": "    "}).status_code == 422


def test_duplicado_ignora_maiusculas_mesmo_com_acento(client, auth):
    admin = auth("ADMIN")
    assert client.post("/distritos", headers=admin, json={"nome": "Água Fria"}).status_code == 201
    assert client.post("/distritos", headers=admin, json={"nome": "ÁGUA FRIA"}).status_code == 409


def test_atualizar_distrito(client, auth, distrito_id):
    admin = auth("ADMIN")
    r = client.put(f"/distritos/{distrito_id}", headers=admin, json={"nome": "Distrito Sul"})
    assert r.status_code == 200 and r.json()["nome"] == "Distrito Sul"
    assert "DISTRITO_ATUALIZADO" in acoes_de_distrito(client, auth)

    assert client.post("/distritos", headers=admin, json={"nome": "Distrito Leste"}).status_code == 201
    assert client.put(f"/distritos/{distrito_id}", headers=admin, json={"nome": "distrito leste"}).status_code == 409
    assert client.put("/distritos/999", headers=admin, json={"nome": "Fantasma"}).status_code == 404

    # mudar só maiúsculas no próprio nome é permitido
    assert client.put(f"/distritos/{distrito_id}", headers=admin, json={"nome": "DISTRITO SUL"}).status_code == 200


def test_atualizar_com_o_mesmo_nome_nao_gera_auditoria(client, auth, distrito_id):
    r = client.put(f"/distritos/{distrito_id}", headers=auth("ADMIN"), json={"nome": "Distrito Sanitário I"})
    assert r.status_code == 200
    assert "DISTRITO_ATUALIZADO" not in acoes_de_distrito(client, auth)


def test_excluir_distrito_sem_unidades(client, auth, distrito_id):
    admin = auth("ADMIN")
    assert client.delete(f"/distritos/{distrito_id}", headers=admin).status_code == 204
    assert client.get("/distritos", headers=admin).json() == []
    assert client.delete(f"/distritos/{distrito_id}", headers=admin).status_code == 404
    assert "DISTRITO_EXCLUIDO" in acoes_de_distrito(client, auth)


def test_nao_exclui_distrito_com_unidades(client, auth, criar_unidade, distrito_id):
    criar_unidade()
    r = client.delete(f"/distritos/{distrito_id}", headers=auth("ADMIN"))
    assert r.status_code == 409 and "1 unidade" in r.json()["detail"]
    assert len(client.get("/distritos", headers=auth("ADMIN")).json()) == 1


def test_aprovacao_recusada_se_o_distrito_foi_excluido(client, auth, distrito_id):
    r = client.post("/solicitacoes", headers=auth("EDITOR_TECNICO"), json={
        "tipo": "INCLUSAO",
        "dados_propostos": {"nome": "UBS Nova", "tipo": "UBS", "distrito_id": distrito_id},
        "justificativa": "Nova unidade",
    })
    assert client.delete(f"/distritos/{distrito_id}", headers=auth("ADMIN")).status_code == 204

    d = client.post(f"/solicitacoes/{r.json()['id']}/decisao", headers=auth("GESTOR_INFO"),
                    json={"resultado": "APROVADA", "justificativa": "Conferido"})
    assert d.status_code == 422 and d.json()["detail"] == "Distrito não encontrado"


def test_somente_admin_altera_distritos(client, auth, distrito_id):
    for papel in ("LEITOR", "EDITOR_TECNICO", "GESTOR_INFO"):
        headers = auth(papel)
        assert client.get("/distritos", headers=headers).status_code == 200
        assert client.post("/distritos", headers=headers, json={"nome": "Novo"}).status_code == 403
        assert client.put(f"/distritos/{distrito_id}", headers=headers, json={"nome": "Novo"}).status_code == 403
        assert client.delete(f"/distritos/{distrito_id}", headers=headers).status_code == 403
