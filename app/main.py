from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401  (registra os modelos)
from app.core.config import settings
from app.core.database import Base, engine
from app.modules.auditoria.router import router as auditoria_router
from app.modules.auth.router import router as auth_router
from app.modules.cnes.router import router as cnes_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.distritos.router import router as distritos_router
from app.modules.solicitacoes.router import router as solicitacoes_router
from app.modules.unidades.router import router as unidades_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # simples para o início; use Alembic quando o esquema estabilizar
    yield


app = FastAPI(title="Governança Cadastral da ESF - Recife", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth_router,
    dashboard_router,
    unidades_router,
    solicitacoes_router,
    cnes_router,
    distritos_router,
    auditoria_router,
):
    app.include_router(router)


@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


# Front-end estático (HTML/CSS/JS) servido na mesma origem da API, sem CORS.
# Fica por último para não sobrepor nenhuma rota da API.
_FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
if _FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND, html=True), name="frontend")
