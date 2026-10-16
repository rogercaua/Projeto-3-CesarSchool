from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Usuario(Base):
    """Espelho local do usuário do Keycloak. Os papéis vêm do token, não do banco."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    keycloak_id: Mapped[str] = mapped_column(String(100), unique=True)
    nome: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(150))
