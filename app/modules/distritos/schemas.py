from pydantic import BaseModel, ConfigDict, Field


class DistritoIn(BaseModel):
    nome: str = Field(min_length=2, max_length=100)


class DistritoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
