from pydantic import BaseModel, ConfigDict, Field


class DistritoIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nome: str = Field(min_length=2, max_length=100)


class DistritoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
