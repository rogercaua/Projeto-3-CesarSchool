from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.deps import exigir
from app.modules.auth.schemas import Papel
from app.modules.cnes import service
from app.modules.cnes.client import CnesClient, get_cnes_client
from app.modules.cnes.schemas import Divergencia, EstabelecimentoCnes

router = APIRouter(prefix="/cnes", tags=["cnes"])


@router.get(
    "/estabelecimentos/{codigo}",
    response_model=EstabelecimentoCnes,
    dependencies=[Depends(exigir(Papel.EDITOR_TECNICO, Papel.GESTOR_INFO, Papel.ADMIN))],
)
def buscar(codigo: str = Path(pattern=r"^\d{7}$"), cnes: CnesClient = Depends(get_cnes_client)):
    """Consulta usada no formulário de solicitação para preencher os dados da unidade."""
    dados = cnes.buscar(codigo)
    if dados is None:
        raise HTTPException(404, "Estabelecimento não encontrado no CNES")
    return EstabelecimentoCnes(codigo=codigo, **dados)


@router.get(
    "/conciliacao",
    response_model=list[Divergencia],
    dependencies=[Depends(exigir(Papel.GESTOR_INFO, Papel.ADMIN))],
)
def conciliacao(db: Session = Depends(get_db), cnes: CnesClient = Depends(get_cnes_client)):
    return service.conciliar(db, cnes)
