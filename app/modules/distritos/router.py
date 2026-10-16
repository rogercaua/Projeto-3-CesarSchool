from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auditoria.service import registrar
from app.modules.auth.deps import Principal, exigir, usuario_atual
from app.modules.auth.schemas import Papel
from app.modules.distritos.models import Distrito
from app.modules.distritos.schemas import DistritoIn, DistritoOut

router = APIRouter(prefix="/distritos", tags=["distritos"])


@router.get("", response_model=list[DistritoOut])
def listar(db: Session = Depends(get_db), _: Principal = Depends(usuario_atual)):
    return db.scalars(select(Distrito).order_by(Distrito.nome)).all()


@router.post("", response_model=DistritoOut, status_code=201)
def criar(
    dados: DistritoIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(exigir(Papel.ADMIN)),
):
    if db.scalar(select(Distrito).where(Distrito.nome == dados.nome)):
        raise HTTPException(409, "Distrito já cadastrado")
    distrito = Distrito(nome=dados.nome)
    db.add(distrito)
    db.flush()
    registrar(db, principal.id, "DISTRITO_CRIADO", "distrito", distrito.id, {"nome": dados.nome})
    db.commit()
    return distrito
