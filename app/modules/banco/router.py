from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.deps import Principal, exigir
from app.modules.auth.schemas import Papel
from app.modules.banco import service

router = APIRouter(prefix="/banco", tags=["banco de dados"])

_PODE_VER = exigir(Papel.GESTOR_INFO, Papel.ADMIN)
_ADMIN = exigir(Papel.ADMIN)


class FuncaoIn(BaseModel):
    argumentos: list[str | float | int | None]


class CancelarIn(BaseModel):
    dias: int = Field(ge=1, le=3650)


@router.get("/objetos")
def objetos(db: Session = Depends(get_db), _: Principal = Depends(_PODE_VER)):
    """Views, triggers, funções e procedimentos, com o SQL de cada um."""
    return service.objetos(db)


@router.get("/views/{nome}")
def consultar_view(nome: str, request: Request, db: Session = Depends(get_db), _: Principal = Depends(_PODE_VER)):
    """Filtros aceitos por view: ver service.VIEWS (ex.: ?status=PENDENTE&inicio=2026-01-01)."""
    return service.consultar_view(db, nome, dict(request.query_params))


@router.post("/funcoes/{nome}")
def executar_funcao(nome: str, dados: FuncaoIn, db: Session = Depends(get_db), _: Principal = Depends(_PODE_VER)):
    return {"resultado": service.executar_funcao(db, nome, dados.argumentos)}


@router.get("/procedimentos/sp_relatorio_periodo")
def relatorio_periodo(
    inicio: date | None = None,
    fim: date | None = None,
    distrito_id: int | None = None,
    db: Session = Depends(get_db),
    _: Principal = Depends(_PODE_VER),
):
    return service.sp_relatorio_periodo(db, inicio, fim, distrito_id)


@router.post("/procedimentos/sp_cancelar_paradas")
def cancelar_paradas(dados: CancelarIn, db: Session = Depends(get_db), principal: Principal = Depends(_ADMIN)):
    ids = service.sp_cancelar_paradas(db, dados.dias, principal.id)
    return {"canceladas": len(ids), "ids": ids}


@router.get("/historico-status")
def historico_status(
    protocolo: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: Principal = Depends(_PODE_VER),
):
    """Efeito dos triggers trg_solicitacao_status_*: cada mudança de status de uma solicitação."""
    return service.historico_status(db, protocolo, limit)
