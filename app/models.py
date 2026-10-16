"""Importa todos os modelos para registrá-los no metadata (create_all, seed, futuras migrações)."""
from app.modules.auditoria.models import AuditoriaEvento  # noqa: F401
from app.modules.auth.models import Usuario  # noqa: F401
from app.modules.distritos.models import Distrito  # noqa: F401
from app.modules.solicitacoes.models import Decisao, Solicitacao  # noqa: F401
from app.modules.unidades.models import Unidade  # noqa: F401
