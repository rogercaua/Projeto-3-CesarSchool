import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.unidades.models import StatusUnidade, Unidade


def listar(
    db: Session,
    q: str | None,
    distrito_id: int | None,
    tipo: str | None,
    status: StatusUnidade | None,
    sem_cnes: bool,
    skip: int,
    limit: int,
) -> tuple[int, list[Unidade]]:
    cond = []
    if q and q.strip():
        termo = q.strip()
        por_id = re.fullmatch(r"[uU](\d+)", termo)  # busca por "U001"
        cond.append(Unidade.id == int(por_id.group(1)) if por_id else Unidade.nome.ilike(f"%{termo}%"))
    if distrito_id is not None:
        cond.append(Unidade.distrito_id == distrito_id)
    if tipo:
        cond.append(Unidade.tipo == tipo)
    if status:
        cond.append(Unidade.status == status)
    if sem_cnes:
        cond.append(Unidade.codigo_cnes.is_(None))

    total = db.scalar(select(func.count()).select_from(Unidade).where(*cond))
    itens = db.scalars(select(Unidade).where(*cond).order_by(Unidade.id).offset(skip).limit(limit)).all()
    return total, list(itens)


def snapshot(unidade: Unidade) -> dict:
    """Foto dos dados da unidade, guardada na decisão antes de aplicar uma mudança."""
    return {
        "nome": unidade.nome,
        "tipo": unidade.tipo,
        "codigo_cnes": unidade.codigo_cnes,
        "distrito_id": unidade.distrito_id,
        "status": unidade.status.value,
        "latitude": unidade.latitude,
        "longitude": unidade.longitude,
        "qtd_equipamentos": unidade.qtd_equipamentos,
        "qtd_servicos": unidade.qtd_servicos,
    }
