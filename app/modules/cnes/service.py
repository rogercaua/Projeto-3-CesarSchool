from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cnes.client import CnesClient
from app.modules.cnes.schemas import Divergencia
from app.modules.unidades.models import StatusUnidade, Unidade

_CAMPOS_COMPARADOS = ("nome", "tipo")


def _norm(texto: str | None) -> str:
    return " ".join((texto or "").split()).casefold()


def conciliar(db: Session, cnes: CnesClient) -> list[Divergencia]:
    """Compara as unidades ativas com o CNES e lista o que não bate."""
    divergencias = []
    unidades = db.scalars(select(Unidade).where(Unidade.status == StatusUnidade.ATIVO).order_by(Unidade.id))

    for u in unidades:
        base = {"unidade_id": u.id, "unidade_nome": u.nome}
        if not u.codigo_cnes:
            divergencias.append(Divergencia(**base, divergencia="SEM_CODIGO_CNES"))
            continue
        oficial = cnes.buscar(u.codigo_cnes)
        if oficial is None:
            divergencias.append(Divergencia(**base, divergencia="NAO_ENCONTRADO_NO_CNES"))
            continue
        for campo in _CAMPOS_COMPARADOS:
            local, remoto = getattr(u, campo), oficial.get(campo)
            if _norm(local) != _norm(remoto):
                divergencias.append(Divergencia(
                    **base, divergencia="CAMPO_DIVERGENTE", campo=campo, valor_local=local, valor_cnes=remoto
                ))
    return divergencias
