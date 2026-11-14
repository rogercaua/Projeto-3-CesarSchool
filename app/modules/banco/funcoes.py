"""Funções SQL do banco.

O SQLite não guarda funções no banco como o PostgreSQL (CREATE FUNCTION). O equivalente é
registrar a função em cada conexão com `create_function`; depois disso ela é chamada no SQL
como qualquer função nativa (ex.: SELECT fn_percentual(3, 4)). As views usam estas funções.
"""
import sqlite3
from datetime import datetime

from sqlalchemy import event
from sqlalchemy.engine import Engine


def _data(valor) -> datetime | None:
    if valor is None:
        return None
    return datetime.fromisoformat(str(valor)).replace(tzinfo=None)


def fn_percentual(parte, total):
    """Percentual com 1 casa decimal; 0 quando o total é zero."""
    return round(100.0 * (parte or 0) / total, 1) if total else 0.0


def fn_dias_entre(inicio, fim):
    """Dias (com 1 casa decimal) entre duas datas; NULL se alguma faltar."""
    a, b = _data(inicio), _data(fim)
    return None if a is None or b is None else round((b - a).total_seconds() / 86400, 1)


def fn_protocolo(solicitacao_id, criada_em):
    """Protocolo legível da solicitação, ex.: SOL-2026-0007."""
    data = _data(criada_em)
    return None if data is None else f"SOL-{data.year}-{int(solicitacao_id):04d}"


# nome -> (função, número de argumentos, descrição para a interface)
FUNCOES = {
    "fn_percentual": (fn_percentual, 2, "Percentual de parte sobre total (parte, total)"),
    "fn_dias_entre": (fn_dias_entre, 2, "Dias entre duas datas (inicio, fim)"),
    "fn_protocolo": (fn_protocolo, 2, "Protocolo da solicitação (id, criada_em)"),
}


@event.listens_for(Engine, "connect")
def _registrar(conexao, _):
    if isinstance(conexao, sqlite3.Connection):
        for nome, (fn, nargs, _desc) in FUNCOES.items():
            conexao.create_function(nome, nargs, fn, deterministic=True)
