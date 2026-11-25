from botocore.exceptions import ClientError

from app.core.config import settings
from app.modules.relatorios import service
from tests.conftest import _StubBoto3


def test_exportar_sem_bucket_configurado_falha(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "s3_bucket", "")
    r = client.post("/relatorios/exportar", headers=auth("ADMIN"))
    assert r.status_code == 500


def test_exportar_envia_csv_para_o_s3(client, auth, s3):
    r = client.post("/relatorios/exportar", headers=auth("GESTOR_INFO"))
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["bucket"] == "bucket-teste"
    assert corpo["chave"].startswith("relatorios/periodo_")
    assert corpo["chave"].endswith(".csv")
    assert corpo["tamanho_bytes"] > 0

    assert len(s3.put_object_chamadas) == 1
    chamada = s3.put_object_chamadas[0]
    assert chamada["Bucket"] == "bucket-teste"
    assert chamada["ContentType"] == "text/csv"
    assert b"unidades_total" in chamada["Body"]

    eventos = client.get("/auditoria", headers=auth("ADMIN")).json()["itens"]
    assert eventos[0]["acao"] == "RELATORIO_EXPORTADO"
    assert eventos[0]["detalhes"]["bucket"] == "bucket-teste"


def test_listar_relatorios_exportados(client, auth, s3):
    client.post("/relatorios/exportar", headers=auth("ADMIN"))
    r = client.get("/relatorios", headers=auth("GESTOR_INFO"))
    assert r.status_code == 200
    itens = r.json()["itens"]
    assert len(itens) == 1
    assert itens[0]["chave"].startswith("relatorios/periodo_")


def test_exportar_exige_papel_de_gestor_ou_admin(client, auth, s3):
    for papel in ("LEITOR", "EDITOR_TECNICO"):
        assert client.post("/relatorios/exportar", headers=auth(papel)).status_code == 403
        assert client.get("/relatorios", headers=auth(papel)).status_code == 403


def test_exportar_propaga_erro_do_s3_como_502(client, auth, monkeypatch):
    class S3ComErro:
        def put_object(self, **kwargs):
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "nope"}}, "PutObject")

    monkeypatch.setattr(settings, "s3_bucket", "bucket-teste")
    monkeypatch.setattr(service, "boto3", _StubBoto3(S3ComErro()))
    r = client.post("/relatorios/exportar", headers=auth("ADMIN"))
    assert r.status_code == 502
