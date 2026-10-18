from datetime import date

import pytest

from conftest import at
from hub.db import events
from hub.people import ValidationError, add_person, deactivate_person
from hub.presence import DEFAULT, effective, presence_board, set_status


def test_no_record_means_out_since_midnight():
    assert effective(None, None, at(10)) == (DEFAULT, at(0, 0))


def test_yesterday_status_resets_today():
    # Review Focus 4
    assert effective("Na sala", at(17, 0, day=18), at(8)) == ("Fora da empresa", at(0, 0))


def test_today_status_kept():
    assert effective("Em reunião", at(10, 15), at(11)) == ("Em reunião", at(10, 15))


def test_set_status_and_board(db):
    kayo = add_person(db, at(7), None, "Kayo")
    ana = add_person(db, at(7), None, "Ana")
    set_status(db, at(10, 15), kayo.id, "Em reunião")
    rows = presence_board(db, at(11))
    assert [(p.name, s, since) for p, s, since in rows] == [
        ("Ana", "Fora da empresa", at(0, 0)),
        ("Kayo", "Em reunião", at(10, 15)),
    ]
    ev = [e for e in events(db, date(2026, 10, 19), date(2026, 10, 19)) if e["kind"] == "presenca"]
    assert [(e["actor_id"], e["detail"]) for e in ev] == [(kayo.id, "Em reunião")]


def test_same_status_does_not_move_since(db):
    kayo = add_person(db, at(7), None, "Kayo")
    set_status(db, at(9), kayo.id, "Na sala")
    set_status(db, at(10), kayo.id, "Na sala")
    assert presence_board(db, at(11))[0][2] == at(9)
    assert len([e for e in events(db, date(2026, 10, 19), date(2026, 10, 19)) if e["kind"] == "presenca"]) == 1


def test_same_status_yesterday_counts_as_new(db):
    kayo = add_person(db, at(7, day=18), None, "Kayo")
    set_status(db, at(9, day=18), kayo.id, "Na sala")
    set_status(db, at(8), kayo.id, "Na sala")
    assert presence_board(db, at(9))[0][1:] == ("Na sala", at(8))


def test_invalid_status_and_inactive_people(db):
    kayo = add_person(db, at(7), None, "Kayo")
    with pytest.raises(ValidationError, match="Status inválido."):
        set_status(db, at(9), kayo.id, "Almoçando")
    deactivate_person(db, at(9), None, kayo.id)
    assert presence_board(db, at(10)) == []
