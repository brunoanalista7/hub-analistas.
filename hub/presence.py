"""Presença: onde cada um está. Sempre marcada pela própria pessoa."""

from datetime import datetime, time

from .db import Database, log_event
from .people import Person, ValidationError, list_people

STATUSES = ("Na sala", "Em reunião", "Pausa", "Fora da empresa")
DEFAULT = "Fora da empresa"


def effective(status: str | None, since: datetime | None, now: datetime) -> tuple[str, datetime]:
    """Status que vale agora. Marcado em outro dia vira "Fora da empresa" desde a meia-noite,
    sem tarefa agendada: é calculado toda vez."""
    midnight = datetime.combine(now.date(), time.min)
    if status is None or since is None or since < midnight:
        return DEFAULT, midnight
    return status, since


def _stored(conn, person_id: int) -> tuple[str | None, datetime | None]:
    r = conn.execute("SELECT status, since FROM presence WHERE person_id = ?", (person_id,)).fetchone()
    return (r["status"], datetime.fromisoformat(r["since"])) if r else (None, None)


def set_status(db: Database, now: datetime, person_id: int, status: str) -> None:
    if status not in STATUSES:
        raise ValidationError("Status inválido.")
    with db.connect() as conn:
        current, _ = effective(*_stored(conn, person_id), now)
        if current == status and _stored(conn, person_id)[0] == status:
            return  # nada mudou: o "desde" continua o mesmo
        conn.execute(
            "INSERT INTO presence(person_id, status, since) VALUES (?, ?, ?) "
            "ON CONFLICT(person_id) DO UPDATE SET status = excluded.status, since = excluded.since",
            (person_id, status, now.isoformat(timespec="seconds")),
        )
        log_event(conn, now, person_id, "presenca", f"pessoa:{person_id}", status)


def presence_board(db: Database, now: datetime) -> list[tuple[Person, str, datetime]]:
    people = list_people(db)
    with db.connect() as conn:
        return [(p, *effective(*_stored(conn, p.id), now)) for p in people]
