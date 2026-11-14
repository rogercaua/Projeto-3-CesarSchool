from sqlalchemy import func, select, text

from app.core.database import Base, SessionLocal, engine
from app.modules.banco.service import instalar
from app.modules.solicitacoes.models import Solicitacao, StatusSolicitacao, TipoSolicitacao
from app.modules.unidades.models import Unidade
from app.seed import TOTAL_SOLICITACOES, Gerador


def test_seed_gera_dados_coerentes():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    instalar(engine)
    with SessionLocal() as db:
        Gerador(db).executar()
        assert db.scalar(select(func.count()).select_from(Solicitacao)) == TOTAL_SOLICITACOES
        assert set(db.scalars(select(Solicitacao.status).distinct())) == set(StatusSolicitacao)
        assert set(db.scalars(select(Solicitacao.tipo).distinct())) == set(TipoSolicitacao)
        # inclusão aprovada vira unidade; CNES nunca se repete
        aprovadas = db.scalars(select(Solicitacao).where(Solicitacao.tipo == TipoSolicitacao.INCLUSAO,
                                                         Solicitacao.status == StatusSolicitacao.APROVADA)).all()
        assert aprovadas and all(s.unidade_id for s in aprovadas)
        cnes = db.scalars(select(Unidade.codigo_cnes).where(Unidade.codigo_cnes.is_not(None))).all()
        assert len(cnes) == len(set(cnes))
        # nada no futuro e cada solicitação com histórico gravado pelo trigger
        assert db.scalar(text("SELECT COUNT(*) FROM decisoes WHERE decidida_em > :agora"),
                         {"agora": str(__import__("datetime").datetime.utcnow())}) == 0
        assert db.scalar(text("SELECT COUNT(DISTINCT solicitacao_id) FROM historico_status")) == TOTAL_SOLICITACOES
