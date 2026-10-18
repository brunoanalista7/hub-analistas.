import json
import threading
from datetime import date, timedelta

import pytest

from conftest import at
from hub.db import Database, events
from hub.demands import RESERVED_TEXT, board, create_demand, delete_demand, is_overdue, move_demand, tv_card, update_demand
from hub.people import ValidationError, add_person, deactivate_person, get_person


@pytest.fixture
def people(db):
    return add_person(db, at(7), None, "Kayo"), add_person(db, at(7), None, "Bianca")


def new(db, owner, title, when=None, **kw):
    return create_demand(db, when or at(8), owner.id, title=title, owner_id=owner.id, **kw)


def test_board_order_overdue_then_due_then_oldest(db, people):
    kayo, _ = people
    a = new(db, kayo, "A sem prazo", at(8))
    b = new(db, kayo, "B prazo 25", at(9), due=date(2026, 10, 25))
    c = new(db, kayo, "C atrasada", at(10), due=date(2026, 10, 17))
    d = new(db, kayo, "D prazo 20", at(11), due=date(2026, 10, 20))
    assert [x.id for x in board(db, at(12))["todo"]] == [c.id, d.id, b.id, a.id]
    assert is_overdue(c, date(2026, 10, 19)) and not is_overdue(d, date(2026, 10, 19))


def test_done_today_only_and_newest_first(db, people):
    kayo, _ = people
    yesterday = new(db, kayo, "Ontem", at(8, day=18))
    move_demand(db, at(23, 59, day=18), kayo.id, yesterday.id, "done")
    first = new(db, kayo, "Primeira")
    second = new(db, kayo, "Segunda")
    move_demand(db, at(9), kayo.id, first.id, "done")
    move_demand(db, at(10), kayo.id, second.id, "done")
    assert [x.title for x in board(db, at(11))["done"]] == ["Segunda", "Primeira"]
    # Review Focus 4: o concluído às 23:59 de ontem não aparece hoje
    assert "Ontem" not in [x.title for x in board(db, at(0, 0))["done"]]


def test_move_back_from_done_clears_done_at(db, people):
    kayo, _ = people
    d = new(db, kayo, "Ida e volta")
    assert move_demand(db, at(9), kayo.id, d.id, "done").done_at == at(9)
    back = move_demand(db, at(10), kayo.id, d.id, "doing")
    assert back.done_at is None and back.column == "doing"


def test_events_record_actor_for_each_change(db, people):
    kayo, bianca = people
    d = new(db, kayo, "Relatório")
    move_demand(db, at(9), bianca.id, d.id, "doing")
    rows = events(db, date(2026, 10, 19), date(2026, 10, 19))
    assert [(r["kind"], r["actor_id"], r["subject"]) for r in rows if r["kind"].startswith("demanda")] == [
        ("demanda_movida", bianca.id, f"demanda:{d.id}"),
        ("demanda_criada", kayo.id, f"demanda:{d.id}"),
    ]


def test_reserved_tv_card_hides_everything_sensitive(db, people):
    # Review Focus 1
    kayo, _ = people
    tomorrow = date(2026, 10, 20)
    d = new(db, kayo, "Comissões RCA", folder="B", requested_by="Diretoria", due=tomorrow, reserved=True)
    card = tv_card(d, get_person(db, kayo.id), date(2026, 10, 19))
    assert card["title"] == RESERVED_TEXT and card["folder"] is None and card["requested_by"] is None
    assert card["due"] == tomorrow.isoformat() and card["reserved"] is True and card["initials"] == "K"
    dumped = json.dumps(card, ensure_ascii=False)
    assert "Comissões" not in dumped and "Diretoria" not in dumped


def test_normal_tv_card(db, people):
    kayo, _ = people
    d = new(db, kayo, "Plano Brisa", folder="C", due=date(2026, 10, 17))
    card = tv_card(d, get_person(db, kayo.id), date(2026, 10, 19))
    assert card["title"] == "Plano Brisa" and card["folder"] == "C" and card["overdue"] is True
    assert card["reserved"] is False


def test_concurrent_moves_do_not_fail(tmp_path, people, db):
    # Review Focus 2: dois PCs mexendo no mesmo cartão
    kayo, bianca = people
    d = new(db, kayo, "Disputada")
    errors = []

    def worker(actor, cols):
        local = Database(db.path)
        try:
            for i in range(50):
                move_demand(local, at(9), actor.id, d.id, cols[i % 2])
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(kayo, ("doing", "todo"))),
               threading.Thread(target=worker, args=(bianca, ("done", "doing")))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    moved = [r for r in events(db, date(2026, 10, 19), date(2026, 10, 19)) if r["kind"] == "demanda_movida"]
    assert len(moved) == 100


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"title": "  "}, "Informe o título."),
        ({"title": "x" * 121}, r"Título muito longo \(máximo 120\)."),
        ({"title": "ok", "folder": "Z"}, "Pasta inválida."),
        ({"title": "ok", "requested_by": "y" * 61}, r"\"Pedido por\" muito longo \(máximo 60\)."),
        ({"title": "ok", "owner_id": 999}, "Escolha o dono da demanda."),
    ],
)
def test_validation_messages(db, people, kwargs, message):
    kayo, _ = people
    fields = {"title": "ok", "owner_id": kayo.id, **kwargs}
    with pytest.raises(ValidationError, match=message):
        create_demand(db, at(8), kayo.id, **fields)


def test_inactive_owner_and_bad_column(db, people):
    kayo, bianca = people
    d = new(db, kayo, "x")
    with pytest.raises(ValidationError, match="Coluna inválida."):
        move_demand(db, at(9), kayo.id, d.id, "arquivo")
    deactivate_person(db, at(9), None, bianca.id)
    with pytest.raises(ValidationError, match="Escolha o dono da demanda."):
        create_demand(db, at(9), kayo.id, title="y", owner_id=bianca.id)


def test_update_and_delete(db, people):
    kayo, bianca = people
    d = new(db, kayo, "Antes")
    u = update_demand(db, at(9), kayo.id, d.id, title="Depois", owner_id=bianca.id, folder="E",
                      requested_by="Rafael", due=None, reserved=False)
    assert (u.title, u.owner_id, u.folder) == ("Depois", bianca.id, "E")
    delete_demand(db, at(10), kayo.id, d.id)
    assert all(d.id not in [x.id for x in col] for col in board(db, at(11)).values())
    with pytest.raises(ValidationError, match="Demanda não encontrada."):
        move_demand(db, at(11), kayo.id, d.id, "doing")


def test_board_filter_by_owner(db, people):
    kayo, bianca = people
    new(db, kayo, "do Kayo")
    new(db, bianca, "do Bianca")
    assert [x.title for x in board(db, at(9), owner_id=bianca.id)["todo"]] == ["do Bianca"]
