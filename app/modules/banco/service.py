"""Views, triggers e procedimentos do banco (SQLite) e as consultas que a interface usa."""
from datetime import date, timedelta
from pathlib import Path
from textwrap import dedent

from fastapi import HTTPException
from sqlalchemy import DateTime, bindparam, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.database import agora
from app.modules.auditoria.service import registrar
from app.modules.banco.funcoes import FUNCOES

_SQL = Path(__file__).parent / "sql"


def instalar(engine: Engine) -> None:
    """Cria (ou recria) views e triggers. Depois do create_all, que cria as tabelas."""
    if engine.dialect.name != "sqlite":
        return  # shortcut: os scripts são de SQLite; outro banco precisa de versões próprias
    bruta = engine.raw_connection()
    try:
        for arquivo in ("views.sql", "triggers.sql"):
            bruta.driver_connection.executescript((_SQL / arquivo).read_text(encoding="utf-8"))
    finally:
        bruta.close()


def _linhas(db: Session, sql: str, **params) -> list[dict]:
    return [dict(r._mapping) for r in db.execute(text(sql), params)]


# ---------- views ----------

# nome da view -> (filtros aceitos e a condição SQL de cada um, ordenação)
VIEWS = {
    "vw_unidades_por_distrito": (
        {"distrito_id": "distrito_id = :distrito_id"},
        "distrito",
    ),
    "vw_solicitacoes_detalhadas": (
        {
            "status": "status = :status",
            "tipo": "tipo = :tipo",
            "distrito_id": "distrito_id = :distrito_id",
            "inicio": "date(criada_em, 'localtime') >= :inicio",
            "fim": "date(criada_em, 'localtime') <= :fim",
        },
        "criada_em DESC",
    ),
    "vw_desempenho_gestores": ({}, "decisoes DESC"),
    "vw_evolucao_mensal": (
        {"inicio": "mes >= substr(:inicio, 1, 7)", "fim": "mes <= substr(:fim, 1, 7)"},
        "mes",
    ),
}


def consultar_view(db: Session, nome: str, filtros: dict, limite: int = 500) -> dict:
    if nome not in VIEWS:
        raise HTTPException(404, "View não encontrada")
    aceitos, ordem = VIEWS[nome]
    usados = {k: v for k, v in filtros.items() if k in aceitos and v not in (None, "")}
    where = " AND ".join(aceitos[k] for k in usados) or "1 = 1"
    # nome, condições e ordem vêm só do dicionário acima; os valores vão como parâmetros
    resultado = db.execute(text(f"SELECT * FROM {nome} WHERE {where} ORDER BY {ordem} LIMIT :limite"),
                           {**usados, "limite": limite + 1})  # +1 para saber se cortou
    linhas = [list(r) for r in resultado]
    return {"colunas": list(resultado.keys()), "linhas": linhas[:limite], "truncado": len(linhas) > limite}


# ---------- procedimentos ----------
# O SQLite não tem CREATE PROCEDURE. Cada procedimento é um bloco de SQL parametrizado
# executado numa única transação, com o mesmo papel de uma stored procedure.

_SP_CANCELAR = text("""
    UPDATE solicitacoes
       SET status = 'CANCELADA', atualizada_em = :agora
     WHERE status IN ('PENDENTE', 'DEVOLVIDA')
       AND atualizada_em < :limite
    RETURNING id
""").bindparams(bindparam("agora", type_=DateTime(timezone=True)),
                bindparam("limite", type_=DateTime(timezone=True)))


def sp_cancelar_paradas(db: Session, dias: int, usuario_id: int) -> list[int]:
    """Cancela solicitações em aberto sem movimentação há mais de `dias` dias.
    O trigger trg_solicitacao_status_mudou registra cada mudança em historico_status."""
    momento = agora()
    ids = sorted(db.scalars(_SP_CANCELAR, {"agora": momento, "limite": momento - timedelta(days=dias)}))
    registrar(db, usuario_id, "PROCEDIMENTO_EXECUTADO", "solicitacao", None,
              {"procedimento": "sp_cancelar_paradas", "dias": dias, "canceladas": ids})
    db.commit()
    return ids


def _periodo(inicio: date | None, fim: date | None) -> tuple[date, date]:
    fim = fim or date.today()
    inicio = inicio or fim - timedelta(days=365)
    if inicio > fim:
        raise HTTPException(422, "A data inicial deve ser anterior à final")
    return inicio, fim


_FILTRO_SOL = ("date(criada_em, 'localtime') BETWEEN :inicio AND :fim "
               "AND (:distrito_id IS NULL OR distrito_id = :distrito_id)")

# Blocos do sp_relatorio_periodo (também exibidos na tela "Consultas e Banco")
_SP_RELATORIO_UNIDADES = """
    SELECT COALESCE(SUM(total_unidades), 0) AS total, COALESCE(SUM(ativas), 0) AS ativas,
           COALESCE(SUM(sem_cnes), 0) AS sem_cnes,
           fn_percentual(SUM(ativas) - SUM(sem_cnes), SUM(ativas)) AS pct_com_cnes
      FROM vw_unidades_por_distrito
     WHERE :distrito_id IS NULL OR distrito_id = :distrito_id"""

_SP_RELATORIO_SOLICITACOES = f"""
    SELECT COUNT(*) AS total,
           SUM(CASE WHEN status = 'APROVADA'  THEN 1 ELSE 0 END) AS aprovadas,
           SUM(CASE WHEN status = 'REJEITADA' THEN 1 ELSE 0 END) AS rejeitadas,
           SUM(CASE WHEN status IN ('PENDENTE', 'DEVOLVIDA') THEN 1 ELSE 0 END) AS em_aberto,
           fn_percentual(SUM(CASE WHEN status = 'APROVADA' THEN 1 ELSE 0 END),
                         SUM(CASE WHEN status IN ('APROVADA', 'REJEITADA') THEN 1 ELSE 0 END)) AS taxa_aprovacao,
           ROUND(AVG(dias_ate_decisao), 1) AS media_dias_decisao
      FROM vw_solicitacoes_detalhadas WHERE {_FILTRO_SOL}"""

# mesmo filtro, com :inicio e :fim do período anterior de mesmo tamanho
_SP_RELATORIO_ANTERIOR = f"SELECT COUNT(*) AS total FROM vw_solicitacoes_detalhadas WHERE {_FILTRO_SOL}"


def sp_relatorio_periodo(db: Session, inicio: date | None, fim: date | None, distrito_id: int | None) -> dict:
    """Indicadores do período, com a variação em relação ao período anterior de mesmo tamanho."""
    inicio, fim = _periodo(inicio, fim)
    p = {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "distrito_id": distrito_id}

    unid = _linhas(db, _SP_RELATORIO_UNIDADES, **p)[0]
    sol = _linhas(db, _SP_RELATORIO_SOLICITACOES, **p)[0]

    dur = fim - inicio
    anterior = _linhas(db, _SP_RELATORIO_ANTERIOR,
                       inicio=(inicio - dur - timedelta(days=1)).isoformat(),
                       fim=(inicio - timedelta(days=1)).isoformat(), distrito_id=distrito_id)[0]["total"]
    variacao = None if not anterior else round(100.0 * (sol["total"] - anterior) / anterior, 1)

    return {
        "inicio": inicio, "fim": fim,
        "unidades_total": unid["total"], "unidades_ativas": unid["ativas"],
        "unidades_sem_cnes": unid["sem_cnes"], "pct_com_cnes": unid["pct_com_cnes"] or 0.0,
        "solicitacoes": sol["total"], "aprovadas": sol["aprovadas"] or 0, "rejeitadas": sol["rejeitadas"] or 0,
        "em_aberto": sol["em_aberto"] or 0, "taxa_aprovacao": sol["taxa_aprovacao"] or 0.0,
        "media_dias_decisao": sol["media_dias_decisao"],
        "solicitacoes_periodo_anterior": anterior, "variacao_pct": variacao,
    }


def series_dashboard(db: Session, inicio: date | None, fim: date | None, distrito_id: int | None) -> dict:
    """Dados dos gráficos do dashboard, todos a partir das views."""
    inicio, fim = _periodo(inicio, fim)
    p = {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "distrito_id": distrito_id}

    def agrupar(campo: str) -> list[dict]:
        return _linhas(db, f"SELECT {campo} AS chave, COUNT(*) AS total FROM vw_solicitacoes_detalhadas "
                           f"WHERE {_FILTRO_SOL} GROUP BY {campo} ORDER BY total DESC", **p)

    return {
        "por_status": agrupar("status"),
        "por_tipo": agrupar("tipo"),
        "por_mes": _linhas(db, f"""
            SELECT strftime('%Y-%m', criada_em, 'localtime') AS mes, COUNT(*) AS criadas,
                   SUM(CASE WHEN status = 'APROVADA' THEN 1 ELSE 0 END) AS aprovadas,
                   SUM(CASE WHEN status = 'REJEITADA' THEN 1 ELSE 0 END) AS rejeitadas
              FROM vw_solicitacoes_detalhadas WHERE {_FILTRO_SOL} GROUP BY mes ORDER BY mes""", **p),
        "por_distrito": _linhas(db, """
            SELECT distrito, ativas, inativas, sem_cnes, pct_com_cnes FROM vw_unidades_por_distrito
             WHERE :distrito_id IS NULL OR distrito_id = :distrito_id ORDER BY distrito""", **p),
        "gestores": _linhas(db, """
            SELECT ug.nome AS gestor, COUNT(*) AS decisoes,
                   SUM(CASE WHEN dc.resultado = 'APROVADA' THEN 1 ELSE 0 END) AS aprovadas,
                   SUM(CASE WHEN dc.resultado = 'DEVOLVIDA' THEN 1 ELSE 0 END) AS devolvidas,
                   SUM(CASE WHEN dc.resultado = 'REJEITADA' THEN 1 ELSE 0 END) AS rejeitadas
              FROM decisoes dc
              JOIN usuarios ug ON ug.id = dc.gestor_id
              JOIN vw_solicitacoes_detalhadas v ON v.solicitacao_id = dc.solicitacao_id
             WHERE date(dc.decidida_em, 'localtime') BETWEEN :inicio AND :fim
               AND (:distrito_id IS NULL OR v.distrito_id = :distrito_id)
             GROUP BY ug.nome ORDER BY decisoes DESC""", **p),
    }


# ---------- objetos e efeitos ----------

PROCEDIMENTOS = {
    "sp_relatorio_periodo": ("Indicadores de um período (inicio, fim, distrito_id), com variação "
                             "sobre o período anterior. Somente leitura; alimenta o dashboard.",
                             ";\n\n".join(dedent(sql).strip() for sql in (
                                 _SP_RELATORIO_UNIDADES, _SP_RELATORIO_SOLICITACOES, _SP_RELATORIO_ANTERIOR))),
    "sp_cancelar_paradas": ("Cancela solicitações PENDENTE/DEVOLVIDA sem movimentação há mais de N dias. "
                            "Dispara trg_solicitacao_status_mudou.", dedent(_SP_CANCELAR.text).strip()),
}


def objetos(db: Session) -> dict:
    return {
        "views": _linhas(db, "SELECT name AS nome, sql FROM sqlite_master WHERE type = 'view' ORDER BY name"),
        "triggers": _linhas(db, "SELECT name AS nome, tbl_name AS tabela, sql FROM sqlite_master "
                                "WHERE type = 'trigger' ORDER BY name"),
        "funcoes": [{"nome": n, "argumentos": a, "descricao": d} for n, (_, a, d) in FUNCOES.items()],
        "procedimentos": [{"nome": n, "descricao": d, "sql": s} for n, (d, s) in PROCEDIMENTOS.items()],
    }


def executar_funcao(db: Session, nome: str, argumentos: list) -> object:
    if nome not in FUNCOES:
        raise HTTPException(404, "Função não encontrada")
    nargs = FUNCOES[nome][1]
    if len(argumentos) != nargs:
        raise HTTPException(422, f"{nome} recebe {nargs} argumento(s)")
    marcadores = ", ".join(f":a{i}" for i in range(nargs))
    try:
        return db.scalar(text(f"SELECT {nome}({marcadores})"), {f"a{i}": v for i, v in enumerate(argumentos)})
    except Exception as erro:  # argumento inválido dentro da função (ex.: data mal formada)
        raise HTTPException(422, f"Erro ao executar {nome}: {erro}")


def historico_status(db: Session, protocolo: str | None, limite: int) -> list[dict]:
    return _linhas(db, """
        SELECT h.id, v.protocolo, h.status_anterior, h.status_novo, h.mudou_em
          FROM historico_status h
          JOIN vw_solicitacoes_detalhadas v ON v.solicitacao_id = h.solicitacao_id
         WHERE :protocolo IS NULL OR v.protocolo = :protocolo
         ORDER BY h.mudou_em DESC, h.id DESC
         LIMIT :limite""", protocolo=protocolo or None, limite=limite)
