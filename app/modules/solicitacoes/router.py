from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.schemas import Pagina
from app.modules.auth.deps import Principal, exigir
from app.modules.auth.schemas import Papel
from app.modules.solicitacoes import service
from app.modules.solicitacoes.models import StatusSolicitacao, TipoSolicitacao
from app.modules.solicitacoes.schemas import (
    DecisaoIn,
    SolicitacaoCreate,
    SolicitacaoDetalhe,
    SolicitacaoOut,
    SolicitacaoReenvio,
)

router = APIRouter(prefix="/solicitacoes", tags=["solicitacoes"])

_PODE_VER = exigir(Papel.EDITOR_TECNICO, Papel.GESTOR_INFO, Papel.ADMIN)
_EDITOR = exigir(Papel.EDITOR_TECNICO)
_GESTOR = exigir(Papel.GESTOR_INFO)


@router.post("", response_model=SolicitacaoOut, status_code=201)
def criar(dados: SolicitacaoCreate, db: Session = Depends(get_db), principal: Principal = Depends(_EDITOR)):
    return service.criar(db, dados, principal)


@router.get("", response_model=Pagina[SolicitacaoOut])
def listar(
    status: StatusSolicitacao | None = None,
    tipo: TipoSolicitacao | None = None,
    unidade_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    principal: Principal = Depends(_PODE_VER),
):
    total, itens = service.listar(db, principal, status, tipo, unidade_id, skip, limit)
    return {"total": total, "itens": itens}


@router.get("/contagem", response_model=dict[str, int])
def contagem(db: Session = Depends(get_db), principal: Principal = Depends(_PODE_VER)):
    """Totais por status, para as abas da Central de Pendências."""
    return service.contar_por_status(db, principal)


@router.get("/{solicitacao_id}", response_model=SolicitacaoDetalhe)
def obter(solicitacao_id: int, db: Session = Depends(get_db), principal: Principal = Depends(_PODE_VER)):
    return service.obter(db, solicitacao_id, principal)


@router.put("/{solicitacao_id}", response_model=SolicitacaoOut)
def reenviar(
    solicitacao_id: int,
    dados: SolicitacaoReenvio,
    db: Session = Depends(get_db),
    principal: Principal = Depends(_EDITOR),
):
    return service.reenviar(db, solicitacao_id, dados, principal)


@router.post("/{solicitacao_id}/decisao", response_model=SolicitacaoDetalhe)
def decidir(
    solicitacao_id: int,
    dados: DecisaoIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(_GESTOR),
):
    return service.decidir(db, solicitacao_id, dados, principal)
