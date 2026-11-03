from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auditoria.service import registrar
from app.modules.auth.deps import Principal, exigir, usuario_atual
from app.modules.auth.schemas import Papel
from app.modules.distritos.models import Distrito
from app.modules.distritos.schemas import DistritoIn, DistritoOut
from app.modules.unidades.models import Unidade

router = APIRouter(prefix="/distritos", tags=["distritos"])

_ADMIN = exigir(Papel.ADMIN)


def _obter(db: Session, distrito_id: int) -> Distrito:
    distrito = db.get(Distrito, distrito_id)
    if distrito is None:
        raise HTTPException(404, "Distrito não encontrado")
    return distrito


def _checar_duplicado(db: Session, nome: str, ignorar_id: int | None = None) -> None:
    """Ignora maiúsculas e minúsculas. Compara em Python para tratar acentos igual em qualquer banco."""
    alvo = nome.casefold()
    for distrito in db.scalars(select(Distrito)):
        if distrito.id != ignorar_id and distrito.nome.casefold() == alvo:
            raise HTTPException(409, "Distrito já cadastrado")


@router.get("", response_model=list[DistritoOut])
def listar(db: Session = Depends(get_db), _: Principal = Depends(usuario_atual)):
    return db.scalars(select(Distrito).order_by(Distrito.nome)).all()


@router.post("", response_model=DistritoOut, status_code=201)
def criar(
    dados: DistritoIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(_ADMIN),
):
    _checar_duplicado(db, dados.nome)
    distrito = Distrito(nome=dados.nome)
    db.add(distrito)
    db.flush()
    registrar(db, principal.id, "DISTRITO_CRIADO", "distrito", distrito.id, {"nome": dados.nome})
    db.commit()
    return distrito


@router.put("/{distrito_id}", response_model=DistritoOut)
def atualizar(
    distrito_id: int,
    dados: DistritoIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(_ADMIN),
):
    distrito = _obter(db, distrito_id)
    if distrito.nome == dados.nome:
        return distrito
    _checar_duplicado(db, dados.nome, ignorar_id=distrito.id)
    anterior = distrito.nome
    distrito.nome = dados.nome
    registrar(db, principal.id, "DISTRITO_ATUALIZADO", "distrito", distrito.id,
              {"nome_anterior": anterior, "nome": dados.nome})
    db.commit()
    return distrito


@router.delete("/{distrito_id}", status_code=204)
def excluir(
    distrito_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(_ADMIN),
):
    distrito = _obter(db, distrito_id)
    vinculadas = db.scalar(select(func.count()).select_from(Unidade).where(Unidade.distrito_id == distrito.id))
    if vinculadas:
        raise HTTPException(409, f"Não é possível excluir: o distrito tem {vinculadas} unidade(s) vinculada(s)")
    registrar(db, principal.id, "DISTRITO_EXCLUIDO", "distrito", distrito.id, {"nome": distrito.nome})
    db.delete(distrito)
    db.commit()
