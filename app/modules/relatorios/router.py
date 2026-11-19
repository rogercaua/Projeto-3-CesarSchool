from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auditoria.service import registrar
from app.modules.auth.deps import Principal, exigir
from app.modules.auth.schemas import Papel
from app.modules.relatorios import service

router = APIRouter(prefix="/relatorios", tags=["relatorios"])

_PODE_EXPORTAR = exigir(Papel.GESTOR_INFO, Papel.ADMIN)


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
