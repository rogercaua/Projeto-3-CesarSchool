from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.security import criar_token_dev
from app.modules.auth.deps import Principal, usuario_atual
from app.modules.auth.schemas import DevLoginIn, TokenOut, UsuarioOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/dev-login", response_model=TokenOut)
def dev_login(dados: DevLoginIn):
    """Login simulado, só existe com AUTH_MODE=dev."""
    if settings.auth_mode != "dev":
        raise HTTPException(404)
    token = criar_token_dev(f"dev:{dados.email}", dados.email, dados.nome, [dados.papel.value])
    return TokenOut(access_token=token)


@router.get("/me", response_model=UsuarioOut)
def me(principal: Principal = Depends(usuario_atual)):
    return UsuarioOut(
        id=principal.id,
        nome=principal.usuario.nome,
        email=principal.usuario.email,
        papeis=sorted(principal.papeis),
    )
