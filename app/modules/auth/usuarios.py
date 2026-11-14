"""CRUD de usuários locais (admin).

Os papéis continuam vindo do token. Um usuário criado aqui recebe o identificador do login
simulado (dev:<e-mail>), então passa a ser ele quem entra com esse e-mail em AUTH_MODE=dev.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auditoria.models import AuditoriaEvento
from app.modules.auditoria.service import registrar
from app.modules.auth.deps import Principal, exigir
from app.modules.auth.models import Usuario
from app.modules.auth.schemas import Papel
from app.modules.solicitacoes.models import Decisao, Solicitacao

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

_ADMIN = exigir(Papel.ADMIN)


class UsuarioIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nome: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=3, max_length=150, pattern=r"^[^@\s]+@[^@\s]+$")


class UsuarioAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    keycloak_id: str


def _obter(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(404, "Usuário não encontrado")
    return usuario


def _checar_email(db: Session, email: str, ignorar_id: int | None = None) -> None:
    existe = db.scalar(select(Usuario.id).where(func.lower(Usuario.email) == email.lower(), Usuario.id != ignorar_id))
    if existe:
        raise HTTPException(409, "Já existe um usuário com este e-mail")


@router.get("", response_model=list[UsuarioAdminOut])
def listar(q: str = "", db: Session = Depends(get_db), _: Principal = Depends(_ADMIN)):
    consulta = select(Usuario).order_by(Usuario.nome)
    if q:
        consulta = consulta.where(or_(Usuario.nome.ilike(f"%{q}%"), Usuario.email.ilike(f"%{q}%")))
    return db.scalars(consulta).all()


@router.post("", response_model=UsuarioAdminOut, status_code=201)
def criar(dados: UsuarioIn, db: Session = Depends(get_db), principal: Principal = Depends(_ADMIN)):
    _checar_email(db, dados.email)
    sub = f"dev:{dados.email}"
    if db.scalar(select(Usuario.id).where(Usuario.keycloak_id == sub)):
        raise HTTPException(409, "Já existe um usuário com este e-mail")
    usuario = Usuario(keycloak_id=sub, nome=dados.nome, email=dados.email)
    db.add(usuario)
    db.flush()
    registrar(db, principal.id, "USUARIO_CRIADO", "usuario", usuario.id, {"nome": dados.nome, "email": dados.email})
    db.commit()
    return usuario


@router.put("/{usuario_id}", response_model=UsuarioAdminOut)
def atualizar(usuario_id: int, dados: UsuarioIn, db: Session = Depends(get_db), principal: Principal = Depends(_ADMIN)):
    usuario = _obter(db, usuario_id)
    _checar_email(db, dados.email, ignorar_id=usuario.id)
    anterior = {"nome": usuario.nome, "email": usuario.email}
    usuario.nome, usuario.email = dados.nome, dados.email
    registrar(db, principal.id, "USUARIO_ATUALIZADO", "usuario", usuario.id,
              {"anterior": anterior, "novo": dados.model_dump()})
    db.commit()
    return usuario


@router.delete("/{usuario_id}", status_code=204)
def excluir(usuario_id: int, db: Session = Depends(get_db), principal: Principal = Depends(_ADMIN)):
    usuario = _obter(db, usuario_id)
    if usuario.id == principal.id:
        raise HTTPException(409, "Você não pode excluir o próprio usuário")
    vinculos = sum(
        db.scalar(select(func.count()).select_from(tabela).where(coluna == usuario.id))
        for tabela, coluna in (
            (Solicitacao, Solicitacao.solicitante_id),
            (Decisao, Decisao.gestor_id),
            (AuditoriaEvento, AuditoriaEvento.usuario_id),
        )
    )
    if vinculos:
        raise HTTPException(409, "Não é possível excluir: o usuário tem solicitações, decisões ou eventos de auditoria")
    registrar(db, principal.id, "USUARIO_EXCLUIDO", "usuario", usuario.id, {"nome": usuario.nome, "email": usuario.email})
    db.delete(usuario)
    db.commit()
