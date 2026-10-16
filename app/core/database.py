from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def agora() -> datetime:
    return datetime.now(timezone.utc)


def _criar_engine(url: str):
    if url.startswith("sqlite"):
        opcoes = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            opcoes["poolclass"] = StaticPool  # mantém o banco em memória entre conexões
        return create_engine(url, **opcoes)
    return create_engine(url, pool_pre_ping=True)


engine = _criar_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
