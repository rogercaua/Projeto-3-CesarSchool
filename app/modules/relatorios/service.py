"""Exportação do relatório de indicadores para armazenamento em nuvem (Amazon S3).

A autenticação com a AWS é feita pelo boto3 (assinatura SigV4 a cada chamada),
usando a cadeia padrão de credenciais do ambiente — inclusive as credenciais
temporárias (access key + secret + session token) do AWS Academy Learner Lab.
"""
import csv
import io
from datetime import date

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.banco.service import sp_relatorio_periodo

_PREFIXO = "relatorios/"


def _cliente_s3():
    if not settings.s3_bucket:
        raise HTTPException(500, "S3_BUCKET não configurado")
    return boto3.client("s3", region_name=settings.aws_region)


def _csv_do_relatorio(relatorio: dict) -> bytes:
    buffer = io.StringIO()
    escritor = csv.DictWriter(buffer, fieldnames=list(relatorio.keys()))
    escritor.writeheader()
    escritor.writerow(relatorio)
    return buffer.getvalue().encode("utf-8-sig")  # BOM: o Excel abre acentuação corretamente


def exportar_relatorio_periodo(
    db: Session, inicio: date | None, fim: date | None, distrito_id: int | None, *, subprefixo: str | None = None
) -> dict:
    """Gera o relatório de indicadores do período (mesmos dados do dashboard) como
    CSV e envia para o bucket configurado em S3_BUCKET.

    `subprefixo` isola exportações feitas por um fluxo específico (ex.: OIDC, com o
    usuário que autorizou) das exportações manuais/M2M, sem mudar o bucket."""
    relatorio = sp_relatorio_periodo(db, inicio, fim, distrito_id)
    conteudo = _csv_do_relatorio(relatorio)
    prefixo = f"{_PREFIXO}{subprefixo}/" if subprefixo else _PREFIXO
    chave = f"{prefixo}periodo_{relatorio['inicio']}_{relatorio['fim']}.csv"

    cliente = _cliente_s3()
    try:
        cliente.put_object(Bucket=settings.s3_bucket, Key=chave, Body=conteudo, ContentType="text/csv")
    except (BotoCoreError, ClientError) as erro:
        raise HTTPException(502, f"Falha ao enviar o relatório para o S3: {erro}")

    return {
        "bucket": settings.s3_bucket,
        "chave": chave,
        "url": f"https://{settings.s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{chave}",
        "tamanho_bytes": len(conteudo),
    }


def listar_exportados(limite: int = 50) -> list[dict]:
    cliente = _cliente_s3()
    try:
        resposta = cliente.list_objects_v2(Bucket=settings.s3_bucket, Prefix=_PREFIXO, MaxKeys=limite)
    except (BotoCoreError, ClientError) as erro:
        raise HTTPException(502, f"Falha ao listar relatórios no S3: {erro}")

    itens = [
        {"chave": o["Key"], "tamanho_bytes": o["Size"], "modificado_em": o["LastModified"]}
        for o in resposta.get("Contents", [])
    ]
    return sorted(itens, key=lambda i: i["modificado_em"], reverse=True)
