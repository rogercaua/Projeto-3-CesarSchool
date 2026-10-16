from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int | None
    usuario_nome: str | None
    acao: str
    entidade: str
    entidade_id: int | None
    detalhes: dict | None
    ocorrido_em: datetime
