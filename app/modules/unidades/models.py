import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, agora


class StatusUnidade(str, enum.Enum):
    ATIVO = "ATIVO"
    INATIVO = "INATIVO"


class Unidade(Base):
    """Cadastro oficial. Só é alterado ao aprovar uma solicitação (ver módulo solicitacoes)."""

    __tablename__ = "unidades"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    tipo: Mapped[str] = mapped_column(String(20))
    codigo_cnes: Mapped[str | None] = mapped_column(String(7), unique=True)
    distrito_id: Mapped[int] = mapped_column(ForeignKey("distritos.id"))
    status: Mapped[StatusUnidade] = mapped_column(
        Enum(StatusUnidade, native_enum=False, length=20), default=StatusUnidade.ATIVO
    )
    latitude: Mapped[float | None]
    longitude: Mapped[float | None]
    qtd_equipamentos: Mapped[int] = mapped_column(default=0)
    qtd_servicos: Mapped[int] = mapped_column(default=0)
    atualizada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    distrito: Mapped["Distrito"] = relationship(lazy="joined")  # noqa: F821

    @property
    def codigo(self) -> str:
        return f"U{self.id:03d}"

    @property
    def distrito_nome(self) -> str:
        return self.distrito.nome
