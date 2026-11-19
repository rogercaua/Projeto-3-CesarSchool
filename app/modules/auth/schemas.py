import enum

from pydantic import BaseModel, Field


class Papel(str, enum.Enum):
    EDITOR_TECNICO = "EDITOR_TECNICO"
    GESTOR_INFO = "GESTOR_INFO"
    ADMIN = "ADMIN"
    LEITOR = "LEITOR"


PAPEIS_VALIDOS = {p.value for p in Papel}


class DevLoginIn(BaseModel):
    email: str
    nome: str
    papel: Papel


class LdapLoginIn(BaseModel):
    usuario: str = Field(min_length=1, max_length=150)
    senha: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: str
    papeis: list[Papel]
