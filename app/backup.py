"""Backup do banco SQLite (continuidade). Uso: python -m app.backup [--destino backups] [--manter 7]

Usa a API de backup do próprio sqlite3, que copia um retrato consistente mesmo com a
aplicação no ar, confere a cópia com PRAGMA integrity_check e mantém só as N mais recentes.
Restaurar: pare a aplicação e copie o arquivo do backup por cima do banco (governanca.db).
"""
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import settings


def fazer_backup(origem: str, destino: Path, manter: int = 7) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"governanca_{datetime.now():%Y%m%d_%H%M%S}.db"
    with sqlite3.connect(origem) as src, sqlite3.connect(arquivo) as dst:
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError(f"Backup corrompido: {arquivo}")
    for antigo in sorted(destino.glob("governanca_*.db"))[:-manter]:
        antigo.unlink()
    return arquivo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--destino", default="backups", type=Path)
    parser.add_argument("--manter", default=7, type=int, help="quantos backups guardar (padrão 7)")
    args = parser.parse_args()

    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise SystemExit("Este script só faz backup de banco SQLite em arquivo. Para PostgreSQL/MySQL use pg_dump/mysqldump.")
    print(f"Backup gravado em {fazer_backup(url.database, args.destino, max(args.manter, 1))}")


if __name__ == "__main__":
    main()
