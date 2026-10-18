from datetime import date

import pytest

from conftest import at
from hub.db import Database, events, log_event
from hub.paths import data_dir


def test_init_is_idempotent_and_uses_wal(db):
    db.init()
    with db.connect() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"people", "demands", "presence", "events"} <= tables


def test_log_and_filter_events(db):
    with db.connect() as conn:
        conn.execute("INSERT INTO people(name, initials, color) VALUES ('Ana', 'A', '#111111')")
        conn.execute("INSERT INTO people(name, initials, color) VALUES ('Bia', 'B', '#222222')")
        conn.execute(
            "INSERT INTO demands(title, owner_id, column_, created_at, updated_at) "
            "VALUES ('Relatório', 2, 'todo', '2026-10-19T08:00:00', '2026-10-19T08:00:00')"
        )
        log_event(conn, at(9), 1, "presenca", "pessoa:1", "Na sala")
        log_event(conn, at(10), 1, "demanda_criada", "demanda:1", "Relatório")
        log_event(conn, at(9, day=17), 1, "presenca", "pessoa:1", "Pausa")
    assert [e["kind"] for e in events(db, date(2026, 10, 19), date(2026, 10, 19))] == ["demanda_criada", "presenca"]
    # Bia não fez nada, mas é dona da demanda citada
    assert [e["kind"] for e in events(db, date(2026, 10, 1), date(2026, 10, 31), person_id=2)] == ["demanda_criada"]


def test_error_inside_connect_rolls_back(db):
    with pytest.raises(RuntimeError):
        with db.connect() as conn:
            log_event(conn, at(9), None, "presenca", "pessoa:1", "x")
            raise RuntimeError("falhou no meio")
    assert events(db, date(2026, 10, 1), date(2026, 10, 31)) == []


def test_data_dir_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HUB_DADOS", str(tmp_path / "dados"))
    assert data_dir() == tmp_path / "dados" and (tmp_path / "dados").is_dir()
