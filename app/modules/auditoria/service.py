from sqlalchemy.orm import Session

from app.modules.auditoria.models import AuditoriaEvento


def registrar(
    db: Session,
    usuario_id: int | None,
    acao: str,
    entidade: str,
    entidade_id: int | None = None,
    detalhes: dict | None = None,
) -> None:
    """Adiciona o evento à sessão. Quem chama faz o commit, junto com a operação auditada."""
    db.add(
        AuditoriaEvento(
            usuario_id=usuario_id,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            detalhes=detalhes,
        )
    )
