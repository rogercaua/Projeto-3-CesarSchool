from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import agora, get_db
from app.modules.auth.deps import Principal, usuario_atual
from app.modules.solicitacoes.models import Solicitacao, StatusSolicitacao
from app.modules.unidades.models import StatusUnidade, Unidade

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class Resumo(BaseModel):
    unidades_ativas: int
    sem_codigo_cnes: int
    solicitacoes_pendentes: int
    atualizadas_no_mes: int


@router.get("/resumo", response_model=Resumo)
def resumo(db: Session = Depends(get_db), _: Principal = Depends(usuario_atual)):
    ativa = Unidade.status == StatusUnidade.ATIVO
    inicio_mes = agora().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def contar(tabela, *cond):
        return db.scalar(select(func.count()).select_from(tabela).where(*cond))

    return Resumo(
        unidades_ativas=contar(Unidade, ativa),
        sem_codigo_cnes=contar(Unidade, ativa, Unidade.codigo_cnes.is_(None)),
        solicitacoes_pendentes=contar(Solicitacao, Solicitacao.status == StatusSolicitacao.PENDENTE),
        atualizadas_no_mes=contar(Unidade, Unidade.atualizada_em >= inicio_mes),
    )
