import os

# Configuração de teste: banco em memória e login simulado (antes de importar o app)
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["AUTH_MODE"] = "dev"
os.environ["JWT_SECRET"] = "segredo-de-teste"

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:  # o lifespan recria as tabelas
        yield c


@pytest.fixture()
def auth(client):
    """auth("GESTOR_INFO") -> headers com token. O mesmo e-mail gera o mesmo usuário."""

    def _headers(papel: str, email: str | None = None) -> dict:
        email = email or f"{papel.lower()}@teste.gov.br"
        r = client.post("/auth/dev-login", json={"email": email, "nome": papel.title(), "papel": papel})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _headers


@pytest.fixture()
def distrito_id(client, auth):
    r = client.post("/distritos", headers=auth("ADMIN"), json={"nome": "Distrito Sanitário I"})
    return r.json()["id"]


@pytest.fixture()
def criar_unidade(client, auth, distrito_id):
    """Cria uma unidade pelo fluxo real: inclusão solicitada pelo editor e aprovada pelo gestor."""

    def _criar(nome="UBS Centro", cnes="2077604") -> int:
        r = client.post("/solicitacoes", headers=auth("EDITOR_TECNICO"), json={
            "tipo": "INCLUSAO",
            "dados_propostos": {"nome": nome, "tipo": "UBS", "codigo_cnes": cnes,
                                "distrito_id": distrito_id, "qtd_servicos": 4},
            "justificativa": "Nova unidade",
        })
        assert r.status_code == 201, r.text
        d = client.post(f"/solicitacoes/{r.json()['id']}/decisao", headers=auth("GESTOR_INFO"),
                        json={"resultado": "APROVADA", "justificativa": "Conferido"})
        assert d.status_code == 200, d.text
        return d.json()["unidade_id"]

    return _criar
