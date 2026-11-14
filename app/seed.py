"""Carga inicial de exemplo: python -m app.seed

Cria distritos e unidades (se o banco estiver vazio) e um histórico de demonstração de
solicitações e decisões dos últimos 10 meses (uma vez só), para o dashboard ter o que mostrar.
"""
import random
from datetime import timedelta

from sqlalchemy import select

import app.models  # noqa: F401
from app.core.database import Base, SessionLocal, agora, engine
from app.modules.auth.models import Usuario
from app.modules.banco.service import instalar
from app.modules.distritos.models import Distrito
from app.modules.solicitacoes.models import (
    Decisao,
    ResultadoDecisao,
    Solicitacao,
    StatusSolicitacao,
    TipoSolicitacao,
)
from app.modules.unidades.models import StatusUnidade, Unidade

DISTRITOS = [f"Distrito Sanitário {n}" for n in ("I", "II", "III", "IV", "V", "VI", "VII", "VIII")]

# nome, tipo, código CNES, índice do distrito, equipamentos, serviços
UNIDADES = [
    ("UBS Vila Madalena", "UBS", "2077604", 0, 14, 8),
    ("AMA Perdizes", "AMA", "9848271", 0, 9, 5),
    ("UBS Saúde Consolação", "UBS", None, 1, 11, 7),
    ("CEU AS Butantã", "CEU AS", "3456781", 2, 8, 6),
    ("CRS Ipiranga", "CRS", None, 3, 10, 9),
    ("UBS Parelheiros I", "UBS", "4567892", 4, 7, 4),
    ("UBS Boa Vista", "UBS", "2345671", 1, 12, 9),
    ("USF Casa Amarela", "UBS", "3456712", 2, 6, 5),
    ("CMS Afogados", "CMS", "4567123", 5, 15, 11),
    ("UBS Ibura", "UBS", None, 5, 5, 3),
    ("AMA/UBS Várzea", "AMA/UBS", "5671234", 3, 9, 7),
    ("UBS Jardim São Paulo", "UBS", "6712345", 6, 8, 6),
    ("CRS Torrões", "CRS", "7123456", 3, 11, 8),
    ("UBS Nova Descoberta", "UBS", None, 7, 4, 3),
    ("UBS Cohab", "UBS", "1234567", 6, 7, 5),
]

USUARIOS_DEMO = [  # (nome, e-mail); o e-mail é o mesmo usado no login simulado
    ("Carla Editora", "carla.editora@recife.gov.br"),
    ("Bruno Editor", "bruno.editor@recife.gov.br"),
    ("Helena Gestora", "helena.gestora@recife.gov.br"),
    ("Marcos Gestor", "marcos.gestor@recife.gov.br"),
]

JUSTIFICATIVAS = ["Atualização após visita técnica", "Correção de dados do CNES", "Unidade reformada",
                  "Mudança de equipe", "Ajuste solicitado pelo distrito"]


def _cadastro_base(db) -> bool:
    if db.query(Distrito).first():
        print("Distritos e unidades já existem; mantidos.")
        return False
    distritos = [Distrito(nome=n) for n in DISTRITOS]
    db.add_all(distritos)
    db.flush()
    db.add_all(
        Unidade(nome=n, tipo=t, codigo_cnes=c, distrito_id=distritos[d].id, qtd_equipamentos=e, qtd_servicos=s)
        for n, t, c, d, e, s in UNIDADES
    )
    db.commit()
    print(f"Criados {len(distritos)} distritos e {len(UNIDADES)} unidades.")
    return True


def _historico_demo(db, cadastro_novo: bool) -> None:
    if db.scalar(select(Usuario.id).where(Usuario.keycloak_id == f"dev:{USUARIOS_DEMO[0][1]}")):
        print("Histórico de demonstração já existe; mantido.")
        return
    rnd = random.Random(42)  # sempre os mesmos dados
    usuarios = [Usuario(keycloak_id=f"dev:{e}", nome=n, email=e) for n, e in USUARIOS_DEMO]
    db.add_all(usuarios)
    db.flush()
    editores, gestores = usuarios[:2], usuarios[2:]
    unidades = db.scalars(select(Unidade)).all()
    hoje = agora()

    for i in range(60):
        criada = hoje - timedelta(days=rnd.randint(0, 300), hours=rnd.randint(0, 23))
        unidade = rnd.choice(unidades)
        tipo = rnd.choices([TipoSolicitacao.ALTERACAO, TipoSolicitacao.INCLUSAO], weights=[4, 1])[0]
        propostos = ({"qtd_servicos": unidade.qtd_servicos + rnd.randint(1, 3)} if tipo == TipoSolicitacao.ALTERACAO
                     else {"nome": f"UBS Demonstração {i}", "tipo": "UBS", "distrito_id": unidade.distrito_id})
        s = Solicitacao(
            tipo=tipo, unidade_id=unidade.id if tipo == TipoSolicitacao.ALTERACAO else None,
            solicitante_id=rnd.choice(editores).id, dados_propostos=propostos,
            dados_atuais={"qtd_servicos": unidade.qtd_servicos} if tipo == TipoSolicitacao.ALTERACAO else None,
            justificativa=rnd.choice(JUSTIFICATIVAS), criada_em=criada, atualizada_em=criada,
        )
        db.add(s)
        db.flush()  # trigger: histórico PENDENTE

        # as mais recentes ficam em aberto; as demais recebem uma decisão (inclusões não aprovam, para não criar unidades)
        if (hoje - criada).days < 12 and rnd.random() < 0.7:
            continue
        opcoes = [ResultadoDecisao.REJEITADA, ResultadoDecisao.DEVOLVIDA]
        if tipo == TipoSolicitacao.ALTERACAO:
            opcoes.insert(0, ResultadoDecisao.APROVADA)
        resultado = rnd.choices(opcoes, weights=[6, 2, 1] if len(opcoes) == 3 else [2, 1])[0]
        decidida = min(criada + timedelta(days=rnd.uniform(0.3, 9)), hoje)
        db.add(Decisao(solicitacao_id=s.id, gestor_id=rnd.choice(gestores).id, resultado=resultado,
                       justificativa="Analisado", decidida_em=decidida))
        s.status, s.atualizada_em = StatusSolicitacao(resultado.value), decidida
        db.flush()  # trigger: histórico da mudança de status

    if cadastro_novo:  # não mexe em unidades que já existiam
        for u in unidades[:2]:
            u.status = StatusUnidade.INATIVO  # para o gráfico de situação por distrito
    db.commit()
    print(f"Criados {len(usuarios)} usuários e 60 solicitações de demonstração.")


def main() -> None:
    Base.metadata.create_all(engine)
    instalar(engine)
    with SessionLocal() as db:
        _historico_demo(db, _cadastro_base(db))


if __name__ == "__main__":
    main()
