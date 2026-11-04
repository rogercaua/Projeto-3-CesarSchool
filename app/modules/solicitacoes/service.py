"""Fluxo: PENDENTE -> (gestor decide) -> APROVADA | REJEITADA | DEVOLVIDA -> (editor reenvia) -> PENDENTE."""
import enum

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import agora
from app.modules.auditoria.service import registrar
from app.modules.auth.deps import Principal
from app.modules.auth.schemas import Papel
from app.modules.distritos.models import Distrito
from app.modules.solicitacoes.models import (
    Decisao,
    ResultadoDecisao,
    Solicitacao,
    StatusSolicitacao,
    TipoSolicitacao,
)
from app.modules.solicitacoes.schemas import (
    CancelamentoIn,
    DadosUnidade,
    DecisaoIn,
    SolicitacaoCreate,
    SolicitacaoReenvio,
)
from app.modules.unidades.models import StatusUnidade, Unidade
from app.modules.unidades.service import snapshot

_OBRIGATORIOS_INCLUSAO = ("nome", "tipo", "distrito_id")
_ANULAVEIS = {"codigo_cnes", "latitude", "longitude"}
_MUDAM_SO_STATUS = {
    TipoSolicitacao.INATIVACAO: StatusUnidade.INATIVO,
    TipoSolicitacao.REATIVACAO: StatusUnidade.ATIVO,
}


# ---------- helpers ----------

def _normalizar(dados: DadosUnidade | None) -> dict:
    return dados.model_dump(mode="json", exclude_unset=True) if dados else {}


def _valor(v):
    return v.value if isinstance(v, enum.Enum) else v


def _validar(db: Session, tipo: TipoSolicitacao, unidade_id: int | None, dados: dict) -> Unidade | None:
    """Regras de conteúdo. Roda na criação, no reenvio e de novo na aprovação."""
    unidade = None
    if tipo == TipoSolicitacao.INCLUSAO:
        if unidade_id is not None:
            raise HTTPException(422, "Inclusão não deve informar unidade_id")
        faltando = [c for c in _OBRIGATORIOS_INCLUSAO if dados.get(c) is None]
        if faltando:
            raise HTTPException(422, f"Campos obrigatórios na inclusão: {', '.join(faltando)}")
    else:
        if unidade_id is None:
            raise HTTPException(422, "Informe o unidade_id")
        unidade = db.get(Unidade, unidade_id)
        if unidade is None:
            raise HTTPException(404, "Unidade não encontrada")
        if tipo == TipoSolicitacao.ALTERACAO and not dados:
            raise HTTPException(422, "Informe ao menos um campo a alterar")
        if tipo == TipoSolicitacao.INATIVACAO and unidade.status == StatusUnidade.INATIVO:
            raise HTTPException(409, "A unidade já está inativa")
        if tipo == TipoSolicitacao.REATIVACAO and unidade.status == StatusUnidade.ATIVO:
            raise HTTPException(409, "A unidade já está ativa")

    nulos = [k for k, v in dados.items() if v is None and k not in _ANULAVEIS]
    if nulos:
        raise HTTPException(422, f"Campos que não aceitam valor nulo: {', '.join(nulos)}")

    if dados.get("distrito_id") is not None and db.get(Distrito, dados["distrito_id"]) is None:
        raise HTTPException(422, "Distrito não encontrado")

    if dados.get("codigo_cnes"):
        outro = db.scalar(
            select(Unidade.id).where(Unidade.codigo_cnes == dados["codigo_cnes"], Unidade.id != (unidade_id or 0))
        )
        if outro is not None:
            raise HTTPException(409, "Este código CNES já pertence a outra unidade")
    return unidade


def _dados_atuais(unidade: Unidade | None, tipo: TipoSolicitacao, dados: dict) -> dict | None:
    if unidade is None:
        return None
    if tipo in _MUDAM_SO_STATUS:
        return {"status": unidade.status.value}
    return {campo: _valor(getattr(unidade, campo)) for campo in dados}


def _converter(dados: dict) -> dict:
    return {k: StatusUnidade(v) if k == "status" and v is not None else v for k, v in dados.items()}


def _aplicar(db: Session, s: Solicitacao) -> dict | None:
    """Atualiza o cadastro oficial. Devolve a foto anterior da unidade (None em inclusão)."""
    dados = s.dados_propostos or {}
    unidade = _validar(db, s.tipo, s.unidade_id, dados)  # o cadastro pode ter mudado desde o pedido

    if s.tipo == TipoSolicitacao.INCLUSAO:
        nova = Unidade(**_converter(dados))
        db.add(nova)
        db.flush()
        s.unidade_id = nova.id
        return None

    anterior = snapshot(unidade)
    if s.tipo in _MUDAM_SO_STATUS:
        unidade.status = _MUDAM_SO_STATUS[s.tipo]
    else:
        for campo, valor in _converter(dados).items():
            setattr(unidade, campo, valor)
    unidade.atualizada_em = agora()
    return anterior


def _escopo(principal: Principal) -> list:
    """Gestor e admin veem tudo; editor vê só as próprias solicitações."""
    if principal.tem(Papel.GESTOR_INFO, Papel.ADMIN):
        return []
    return [Solicitacao.solicitante_id == principal.id]


# ---------- operações ----------

def criar(db: Session, dados: SolicitacaoCreate, principal: Principal) -> Solicitacao:
    propostos = {} if dados.tipo in _MUDAM_SO_STATUS else _normalizar(dados.dados_propostos)
    unidade = _validar(db, dados.tipo, dados.unidade_id, propostos)

    s = Solicitacao(
        tipo=dados.tipo,
        unidade_id=dados.unidade_id,
        solicitante_id=principal.id,
        dados_atuais=_dados_atuais(unidade, dados.tipo, propostos),
        dados_propostos=propostos or None,
        justificativa=dados.justificativa,
    )
    db.add(s)
    db.flush()
    registrar(db, principal.id, "SOLICITACAO_CRIADA", "solicitacao", s.id,
              {"protocolo": s.protocolo, "tipo": s.tipo.value, "justificativa": s.justificativa})
    db.commit()
    return s


def obter(db: Session, solicitacao_id: int, principal: Principal) -> Solicitacao:
    s = db.get(Solicitacao, solicitacao_id)
    if s is None:
        raise HTTPException(404, "Solicitação não encontrada")
    if not principal.tem(Papel.GESTOR_INFO, Papel.ADMIN) and s.solicitante_id != principal.id:
        raise HTTPException(403, "Você só pode ver as suas próprias solicitações")
    return s


def listar(
    db: Session,
    principal: Principal,
    status: StatusSolicitacao | None,
    tipo: TipoSolicitacao | None,
    unidade_id: int | None,
    skip: int,
    limit: int,
) -> tuple[int, list[Solicitacao]]:
    cond = _escopo(principal)
    if status:
        cond.append(Solicitacao.status == status)
    if tipo:
        cond.append(Solicitacao.tipo == tipo)
    if unidade_id is not None:
        cond.append(Solicitacao.unidade_id == unidade_id)

    total = db.scalar(select(func.count()).select_from(Solicitacao).where(*cond))
    itens = db.scalars(
        select(Solicitacao).where(*cond).order_by(Solicitacao.id.desc()).offset(skip).limit(limit)
    ).all()
    return total, list(itens)


def contar_por_status(db: Session, principal: Principal) -> dict[str, int]:
    linhas = db.execute(
        select(Solicitacao.status, func.count()).where(*_escopo(principal)).group_by(Solicitacao.status)
    ).all()
    contagem = {s.value: 0 for s in StatusSolicitacao}
    for status, n in linhas:
        contagem[status.value] = n
    contagem["TODOS"] = sum(contagem.values())
    return contagem


def reenviar(db: Session, solicitacao_id: int, dados: SolicitacaoReenvio, principal: Principal) -> Solicitacao:
    s = obter(db, solicitacao_id, principal)
    if s.solicitante_id != principal.id:
        raise HTTPException(403, "Só quem abriu a solicitação pode reenviá-la")
    if s.status != StatusSolicitacao.DEVOLVIDA:
        raise HTTPException(409, "Só é possível reenviar solicitações devolvidas")

    propostos = s.dados_propostos or {}
    if s.tipo not in _MUDAM_SO_STATUS and dados.dados_propostos is not None:
        propostos = _normalizar(dados.dados_propostos)
    unidade = _validar(db, s.tipo, s.unidade_id, propostos)

    s.dados_propostos = propostos or None
    s.dados_atuais = _dados_atuais(unidade, s.tipo, propostos)
    if dados.justificativa:
        s.justificativa = dados.justificativa
    s.status = StatusSolicitacao.PENDENTE
    s.atualizada_em = agora()
    registrar(db, principal.id, "SOLICITACAO_REENVIADA", "solicitacao", s.id, {"protocolo": s.protocolo})
    db.commit()
    return s


def cancelar(db: Session, solicitacao_id: int, dados: CancelamentoIn, principal: Principal) -> Solicitacao:
    s = obter(db, solicitacao_id, principal)
    if s.solicitante_id != principal.id:
        raise HTTPException(403, "Só quem abriu a solicitação pode cancelá-la")
    if s.status not in (StatusSolicitacao.PENDENTE, StatusSolicitacao.DEVOLVIDA):
        raise HTTPException(409, f"Não é possível cancelar: a solicitação já está {s.status.value}")

    s.status = StatusSolicitacao.CANCELADA
    s.atualizada_em = agora()
    registrar(db, principal.id, "SOLICITACAO_CANCELADA", "solicitacao", s.id,
              {"protocolo": s.protocolo, "justificativa": dados.justificativa})
    db.commit()
    return s


def decidir(db: Session, solicitacao_id: int, dados: DecisaoIn, principal: Principal) -> Solicitacao:
    s = db.get(Solicitacao, solicitacao_id)
    if s is None:
        raise HTTPException(404, "Solicitação não encontrada")
    if s.status != StatusSolicitacao.PENDENTE:
        raise HTTPException(409, f"A solicitação já está {s.status.value}")
    if s.solicitante_id == principal.id:
        raise HTTPException(403, "Separação de funções: você não pode decidir a sua própria solicitação")

    anterior = _aplicar(db, s) if dados.resultado == ResultadoDecisao.APROVADA else None

    s.status = StatusSolicitacao(dados.resultado.value)
    s.atualizada_em = agora()
    db.add(Decisao(
        solicitacao_id=s.id,
        gestor_id=principal.id,
        resultado=dados.resultado,
        justificativa=dados.justificativa,
        snapshot_anterior=anterior,
    ))
    registrar(db, principal.id, f"SOLICITACAO_{dados.resultado.value}", "solicitacao", s.id,
              {"protocolo": s.protocolo, "justificativa": dados.justificativa})
    db.commit()
    db.refresh(s)  # recarrega as decisões
    return s
