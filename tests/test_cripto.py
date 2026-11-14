import pytest
from cryptography.exceptions import InvalidTag
from sqlalchemy import text

from app.core.crypto import cifrar, decifrar
from app.core.database import engine


def test_justificativa_fica_cifrada_no_banco_e_legivel_na_api(client, auth, criar_unidade):
    criar_unidade()  # justificativas "Nova unidade" e "Conferido"
    with engine.connect() as c:
        brutos = [r[0] for r in c.execute(text(
            "SELECT justificativa FROM solicitacoes UNION ALL SELECT justificativa FROM decisoes "
            "UNION ALL SELECT detalhes FROM auditoria_eventos WHERE detalhes IS NOT NULL"))]
    assert brutos and all(b.startswith("enc:v1:") for b in brutos)
    assert not any("Nova unidade" in b or "Conferido" in b for b in brutos)

    lista = client.get("/solicitacoes", headers=auth("GESTOR_INFO")).json()
    item = lista["itens"][0] if "itens" in lista else lista[0]
    s = client.get(f"/solicitacoes/{item['id']}", headers=auth("GESTOR_INFO")).json()
    assert s["justificativa"] == "Nova unidade"


def test_cifra_usa_nonce_novo_e_detecta_adulteracao():
    a, b = cifrar("segredo"), cifrar("segredo")
    assert a != b and decifrar(a) == "segredo"
    adulterado = a[:-4] + ("AAAA" if not a.endswith("AAAA") else "BBBB")
    with pytest.raises(InvalidTag):
        decifrar(adulterado)


def test_linhas_antigas_em_texto_puro_continuam_legiveis():
    assert decifrar("justificativa antiga") == "justificativa antiga"
    assert decifrar('{"a": 1}') == {"a": 1}


def test_texto_antigo_que_parece_json_nao_quebra_a_leitura():
    assert decifrar("[URGENTE] trocar CNES") == "[URGENTE] trocar CNES"


def test_modo_keycloak_recusa_a_chave_de_desenvolvimento():
    from pydantic import ValidationError

    from app.core.config import Settings

    sso = {"auth_mode": "keycloak", "keycloak_issuer": "https://sso.exemplo/realms/x", "keycloak_client_id": "web"}
    with pytest.raises(ValidationError, match="CRIPTO_CHAVE"):
        Settings(**sso)
    assert Settings(**sso, cripto_chave="A" * 43 + "=")
