from datetime import datetime

from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, agora


class AuditoriaEvento(Base):
    __tablename__ = "auditoria_eventos"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    acao: Mapped[str] = mapped_column(String(50))
    entidade: Mapped[str] = mapped_column(String(50))
    entidade_id: Mapped[int | None]
    detalhes: Mapped[dict | None] = mapped_column(JSON)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    usuario: Mapped[Optional["Usuario"]] = relationship(lazy="joined")  # noqa: F821

    @property
    def usuario_nome(self) -> str | None:
        return self.usuario.nome if self.usuario else None


@event.listens_for(AuditoriaEvento, "before_update")
@event.listens_for(AuditoriaEvento, "before_delete")
def _auditoria_imutavel(*_):
    raise RuntimeError("Eventos de auditoria são imutáveis")
