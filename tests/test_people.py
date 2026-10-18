from datetime import date

import pytest

from conftest import at
from hub.db import events
from hub.people import PALETTE, ValidationError, add_person, deactivate_person, get_person, list_people, update_person


def test_default_initials_and_distinct_colors(db):
    a = add_person(db, at(8), None, "Ana Clara")
    b = add_person(db, at(8), None, "Kayo")
    assert (a.initials, b.initials) == ("AC", "K")
    assert a.color == PALETTE[0] and b.color == PALETTE[1]


def test_freed_color_is_reused(db):
    a = add_person(db, at(8), None, "Ana")
    add_person(db, at(8), None, "Bia")
    deactivate_person(db, at(9), None, a.id)
    assert add_person(db, at(10), None, "Caio").color == PALETTE[0]


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"name": "  "}, "Informe o nome."),
        ({"name": "Ana", "initials": "ABCD"}, "Use de 1 a 3 letras nas iniciais."),
        ({"name": "Ana", "color": "vermelho"}, "Cor inválida."),
    ],
)
def test_validation(db, kwargs, message):
    with pytest.raises(ValidationError, match=message):
        add_person(db, at(8), None, **kwargs)


def test_duplicate_name(db):
    add_person(db, at(8), None, "Ana")
    with pytest.raises(ValidationError, match="Já existe alguém com esse nome."):
        add_person(db, at(8), None, "ana")


def test_update_and_deactivate_with_events(db):
    a = add_person(db, at(8), None, "Ana")
    update_person(db, at(9), a.id, a.id, initials="AN", color="#123456")
    assert get_person(db, a.id).initials == "AN"
    deactivate_person(db, at(10), None, a.id)
    assert list_people(db) == [] and [p.name for p in list_people(db, active_only=False)] == ["Ana"]
    kinds = [e["kind"] for e in events(db, date(2026, 10, 19), date(2026, 10, 19))]
    assert kinds == ["pessoa_desativada", "pessoa_editada", "pessoa_criada"]
