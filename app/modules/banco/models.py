from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HistoricoStatus(Base):
    """Preenchida só pelos triggers trg_solicitacao_status_* (ver sql/triggers.sql)."""

    __tablename__ = "historico_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    solicitacao_id: Mapped[int] = mapped_column(ForeignKey("solicitacoes.id"))
    status_anterior: Mapped[str | None] = mapped_column(String(20))
    status_novo: Mapped[str] = mapped_column(String(20))
    mudou_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
