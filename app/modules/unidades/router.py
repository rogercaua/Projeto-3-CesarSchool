from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.schemas import Pagina
from app.modules.auth.deps import Principal, usuario_atual
from app.modules.unidades import service
from app.modules.unidades.models import StatusUnidade, Unidade
from app.modules.unidades.schemas import UnidadeOut

# Somente leitura: o cadastro oficial muda apenas por solicitação aprovada.
router = APIRouter(prefix="/unidades", tags=["unidades"])


@router.get("", response_model=Pagina[UnidadeOut])
def listar(
    q: str | None = Query(None, description="Nome ou ID (ex.: U001)"),
    distrito_id: int | None = None,
    tipo: str | None = None,
    status: StatusUnidade | None = None,
    sem_cnes: bool = False,
    skip: int = Query(0, ge=0),
    # shortcut: os seletores do front pedem todas as unidades de uma vez; acima de 1000, trocar por busca
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: Principal = Depends(usuario_atual),
):
    total, itens = service.listar(db, q, distrito_id, tipo, status, sem_cnes, skip, limit)
    return {"total": total, "itens": itens}


@router.get("/{unidade_id}", response_model=UnidadeOut)
def obter(unidade_id: int, db: Session = Depends(get_db), _: Principal = Depends(usuario_atual)):
    unidade = db.get(Unidade, unidade_id)
    if unidade is None:
        raise HTTPException(404, "Unidade não encontrada")
    return unidade
