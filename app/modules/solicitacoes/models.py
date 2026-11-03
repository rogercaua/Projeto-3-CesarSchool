import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, agora


class TipoSolicitacao(str, enum.Enum):
    INCLUSAO = "INCLUSAO"
    ALTERACAO = "ALTERACAO"
    INATIVACAO = "INATIVACAO"
    REATIVACAO = "REATIVACAO"


class StatusSolicitacao(str, enum.Enum):
    PENDENTE = "PENDENTE"  # aguardando análise do gestor
    DEVOLVIDA = "DEVOLVIDA"  # gestor pediu correção; o editor reenvia
    APROVADA = "APROVADA"
    REJEITADA = "REJEITADA"


class ResultadoDecisao(str, enum.Enum):
    APROVADA = "APROVADA"
    DEVOLVIDA = "DEVOLVIDA"
    REJEITADA = "REJEITADA"


class Solicitacao(Base):
    __tablename__ = "solicitacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoSolicitacao] = mapped_column(Enum(TipoSolicitacao, native_enum=False, length=20))
    status: Mapped[StatusSolicitacao] = mapped_column(
        Enum(StatusSolicitacao, native_enum=False, length=20), default=StatusSolicitacao.PENDENTE
    )
    unidade_id: Mapped[int | None] = mapped_column(ForeignKey("unidades.id"))  # nulo até aprovar uma inclusão
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    dados_atuais: Mapped[dict | None] = mapped_column(JSON)  # valores vigentes dos campos que mudam
    dados_propostos: Mapped[dict | None] = mapped_column(JSON)
    justificativa: Mapped[str] = mapped_column(Text)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    solicitante: Mapped["Usuario"] = relationship(lazy="joined")  # noqa: F821
    unidade: Mapped[Optional["Unidade"]] = relationship(lazy="joined")  # noqa: F821
    decisoes: Mapped[list["Decisao"]] = relationship(
        back_populates="solicitacao", order_by="Decisao.id"
    )

    @property
    def protocolo(self) -> str:
        return f"SOL-{self.criada_em.year}-{self.id:04d}"

    @property
    def solicitante_nome(self) -> str:
        return self.solicitante.nome

    @property
    def unidade_nome(self) -> str | None:
        if self.unidade is not None:
            return self.unidade.nome
        return (self.dados_propostos or {}).get("nome")  # inclusão ainda sem unidade

    @property
    def unidade_cnes(self) -> str | None:
        if self.unidade is not None:
            return self.unidade.codigo_cnes
        return (self.dados_propostos or {}).get("codigo_cnes")


class Decisao(Base):
    __tablename__ = "decisoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    solicitacao_id: Mapped[int] = mapped_column(ForeignKey("solicitacoes.id"))
    gestor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    resultado: Mapped[ResultadoDecisao] = mapped_column(Enum(ResultadoDecisao, native_enum=False, length=20))
    justificativa: Mapped[str] = mapped_column(Text)
    # Versão anterior da unidade, guardada ao aprovar (substitui uma tabela de histórico à parte)
    snapshot_anterior: Mapped[dict | None] = mapped_column(JSON)
    decidida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    solicitacao: Mapped["Solicitacao"] = relationship(back_populates="decisoes")
    gestor: Mapped["Usuario"] = relationship(lazy="joined")  # noqa: F821

    @property
    def gestor_nome(self) -> str:
        return self.gestor.nome
