import enum

from pydantic import BaseModel


class Papel(str, enum.Enum):
    EDITOR_TECNICO = "EDITOR_TECNICO"
    GESTOR_INFO = "GESTOR_INFO"
    ADMIN = "ADMIN"
    LEITOR = "LEITOR"


class DevLoginIn(BaseModel):
    email: str
    nome: str
    papel: Papel


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: str
    papeis: list[Papel]
