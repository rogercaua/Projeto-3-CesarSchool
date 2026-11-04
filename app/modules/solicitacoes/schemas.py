from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.solicitacoes.models import ResultadoDecisao, StatusSolicitacao, TipoSolicitacao
from app.modules.unidades.models import StatusUnidade


class DadosUnidade(BaseModel):
    """Campos da unidade que uma solicitação pode propor. Só o que for enviado é alterado."""

    model_config = ConfigDict(extra="forbid")

    nome: str | None = Field(None, min_length=2, max_length=150)
    tipo: str | None = Field(None, min_length=2, max_length=20)
    codigo_cnes: str | None = Field(None, pattern=r"^\d{7}$")
    distrito_id: int | None = None
    status: StatusUnidade | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    qtd_equipamentos: int | None = Field(None, ge=0)
    qtd_servicos: int | None = Field(None, ge=0)


class SolicitacaoCreate(BaseModel):
    tipo: TipoSolicitacao
    unidade_id: int | None = None  # obrigatório em alteração e inativação
    dados_propostos: DadosUnidade | None = None  # ignorado em inativação
    justificativa: str = Field(min_length=3)


class SolicitacaoReenvio(BaseModel):
    """Correção feita pelo editor após a devolução. Se enviados, os dados substituem os anteriores."""

    dados_propostos: DadosUnidade | None = None
    justificativa: str | None = Field(None, min_length=3)


class CancelamentoIn(BaseModel):
    justificativa: str = Field(min_length=3)


class DecisaoIn(BaseModel):
    resultado: ResultadoDecisao
    justificativa: str = Field(min_length=3)  # obrigatória em qualquer decisão


class DecisaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resultado: ResultadoDecisao
    justificativa: str
    gestor_id: int
    gestor_nome: str
    snapshot_anterior: dict | None
    decidida_em: datetime


class SolicitacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    protocolo: str
    tipo: TipoSolicitacao
    status: StatusSolicitacao
    unidade_id: int | None
    unidade_nome: str | None
    unidade_cnes: str | None
    solicitante_id: int
    solicitante_nome: str
    dados_atuais: dict | None
    dados_propostos: dict | None
    justificativa: str
    criada_em: datetime
    atualizada_em: datetime


class SolicitacaoDetalhe(SolicitacaoOut):
    decisoes: list[DecisaoOut]
