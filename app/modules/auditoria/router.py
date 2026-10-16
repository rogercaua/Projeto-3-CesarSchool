from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.schemas import Pagina
from app.modules.auditoria.models import AuditoriaEvento
from app.modules.auditoria.schemas import AuditoriaOut
from app.modules.auth.deps import exigir
from app.modules.auth.schemas import Papel

router = APIRouter(prefix="/auditoria", tags=["auditoria"], dependencies=[Depends(exigir(Papel.ADMIN))])


@router.get("", response_model=Pagina[AuditoriaOut])
def listar(
    entidade: str | None = None,
    entidade_id: int | None = None,
    usuario_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    cond = []
    if entidade:
        cond.append(AuditoriaEvento.entidade == entidade)
    if entidade_id is not None:
        cond.append(AuditoriaEvento.entidade_id == entidade_id)
    if usuario_id is not None:
        cond.append(AuditoriaEvento.usuario_id == usuario_id)

    total = db.scalar(select(func.count()).select_from(AuditoriaEvento).where(*cond))
    itens = db.scalars(
        select(AuditoriaEvento).where(*cond).order_by(AuditoriaEvento.id.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "itens": itens}
