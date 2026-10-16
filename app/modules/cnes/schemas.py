from typing import Literal

from pydantic import BaseModel


class EstabelecimentoCnes(BaseModel):
    codigo: str
    nome: str
    tipo: str


class Divergencia(BaseModel):
    unidade_id: int
    unidade_nome: str
    divergencia: Literal["SEM_CODIGO_CNES", "NAO_ENCONTRADO_NO_CNES", "CAMPO_DIVERGENTE"]
    campo: str | None = None
    valor_local: str | None = None
    valor_cnes: str | None = None
