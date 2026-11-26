from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auditoria.service import registrar
from app.modules.auth import oauth2_m2m, oidc_export
from app.modules.auth.deps import Principal, exigir, exigir_escopo_m2m
from app.modules.auth.schemas import Papel
from app.modules.relatorios import service

router = APIRouter(prefix="/relatorios", tags=["relatorios"])
_COOKIE_ESTADO_OIDC = "oidc_export_estado"

_PODE_EXPORTAR = exigir(Papel.GESTOR_INFO, Papel.ADMIN)
_PODE_EXPORTAR_M2M = exigir_escopo_m2m("relatorios:exportar")


@router.post("/exportar")
def exportar(
    inicio: date | None = None,
    fim: date | None = None,
    distrito_id: int | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(_PODE_EXPORTAR),
):
    """Gera o relatório de indicadores do período (mesmos dados do dashboard) e envia para o S3."""
    resultado = service.exportar_relatorio_periodo(db, inicio, fim, distrito_id)
    registrar(db, principal.id, "RELATORIO_EXPORTADO", "relatorio", None,
              {"bucket": resultado["bucket"], "chave": resultado["chave"]})
    db.commit()
    return resultado


@router.get("")
def listar(_: Principal = Depends(_PODE_EXPORTAR)):
    """Lista os relatórios já exportados para o S3."""
    return {"itens": service.listar_exportados()}


@router.post("/exportar-m2m")
def exportar_m2m(
    inicio: date | None = None,
    fim: date | None = None,
    distrito_id: int | None = None,
    db: Session = Depends(get_db),
    cliente: oauth2_m2m.ClientM2M = Depends(_PODE_EXPORTAR_M2M),
):
    """Mesma exportação para o S3, mas autorizada via OAuth2 M2M (client_credentials):
    quem chama é outro serviço, não uma pessoa logada — por isso o token é validado
    pelo escopo do client (`relatorios:exportar`), não pelo papel de um usuário."""
    resultado = service.exportar_relatorio_periodo(db, inicio, fim, distrito_id)
    registrar(db, None, "RELATORIO_EXPORTADO_M2M", "relatorio", None,
              {"bucket": resultado["bucket"], "chave": resultado["chave"], "client_id": cliente.client_id})
    db.commit()
    return resultado


@router.get("/exportar-oidc/iniciar")
def exportar_oidc_iniciar():
    """Inicia a exportação via OIDC (Authorization Code + PKCE): redireciona o navegador
    pro login no Authorization Server (Keycloak, no papel do Google Drive do enunciado).
    A pessoa autoriza; o ID token devolvido na volta identifica quem exportou."""
    try:
        url, cookie_estado = oidc_export.iniciar_autorizacao()
    except oidc_export.OidcExportError as erro:
        raise HTTPException(500, str(erro))
    resposta = RedirectResponse(url)
    resposta.set_cookie(_COOKIE_ESTADO_OIDC, cookie_estado, httponly=True, max_age=300)
    return resposta


@router.get("/oidc/callback")
def exportar_oidc_callback(code: str, state: str, request: Request, db: Session = Depends(get_db)):
    """Recebe a volta do Authorization Server, valida a identidade de quem autorizou e
    dispara a mesma exportação para o S3 usada pelo fluxo manual/M2M, sob um prefixo
    identificado pelo usuário (distinto do M2M, que não tem usuário por trás)."""
    try:
        identidade = oidc_export.concluir_autorizacao(code, state, request.cookies.get(_COOKIE_ESTADO_OIDC))
    except oidc_export.OidcExportError as erro:
        raise HTTPException(401, str(erro))

    resultado = service.exportar_relatorio_periodo(db, None, None, None, subprefixo=f"oidc/{identidade.username}")
    registrar(db, None, "RELATORIO_EXPORTADO_OIDC", "relatorio", None,
              {"bucket": resultado["bucket"], "chave": resultado["chave"], "usuario_oidc": identidade.username})
    db.commit()
    resposta = JSONResponse(resultado)
    resposta.delete_cookie(_COOKIE_ESTADO_OIDC)
    return resposta
