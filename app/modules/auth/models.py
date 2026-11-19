from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

usuario_grupo = Table(
    "usuario_grupo",
    Base.metadata,
    Column("usuario_id", ForeignKey("usuarios.id"), primary_key=True),
    Column("grupo_id", ForeignKey("grupos.id"), primary_key=True),
)


class Grupo(Base):
    """Espelho local de um grupo/papel vindo do IdP (nome igual ao enum Papel)."""

    __tablename__ = "grupos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(50), unique=True)


class Usuario(Base):
    """Espelho local do usuário vindo do IdP (Keycloak ou LDAP). O identificador
    externo (keycloak_id) também é usado para o login simulado (dev:<e-mail>)
    e para o login LDAP (ldap:<username>)."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    keycloak_id: Mapped[str] = mapped_column(String(100), unique=True)
    nome: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(150))
    grupos: Mapped[list[Grupo]] = relationship(secondary=usuario_grupo)
