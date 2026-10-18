"""Cópia de segurança diária do banco (os últimos 14 dias)."""

import sqlite3
from datetime import date
from pathlib import Path

KEEP_DAYS = 14


def make_backup(db_path: Path, dest: Path, today: date, keep: int = KEEP_DAYS) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"hub-{today.isoformat()}.db"
    # a API de backup do SQLite copia com segurança mesmo com o servidor gravando
    source, copy = sqlite3.connect(db_path), sqlite3.connect(target)
    try:
        source.backup(copy)
    finally:
        copy.close()
        source.close()
    for old in sorted(dest.glob("hub-*.db"))[:-keep]:
        old.unlink()
    return target
