from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.unidades.models import StatusUnidade


class UnidadeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nome: str
    tipo: str
    codigo_cnes: str | None
    distrito_id: int
    distrito_nome: str
    status: StatusUnidade
    latitude: float | None
    longitude: float | None
    qtd_equipamentos: int
    qtd_servicos: int
    atualizada_em: datetime
