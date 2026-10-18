from datetime import date

import pytest
from fastapi.testclient import TestClient

from conftest import at
from hub.demands import board, create_demand
from hub.people import add_person, deactivate_person, list_people
from hub.presence import presence_board
from hub.web.app import create_app

BASE = "http://hub-sala:8800"


@pytest.fixture
def env(db):
    kayo = add_person(db, at(7), None, "Kayo")
    bianca = add_person(db, at(7), None, "Bianca")
    client = TestClient(create_app(db, clock=lambda: at(12)), base_url=BASE)
    return client, db, kayo, bianca


def login(c, person):
    r = c.post("/entrar", data={"person_id": str(person.id)}, follow_redirects=False)
    assert r.status_code == 303
    return c


def test_without_cookie_goes_to_entrar(env):
    c, *_ = env
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/entrar"
    assert "Kayo" in c.get("/entrar").text


def test_create_demand_and_see_it(env):
    c, db, kayo, bianca = env
    login(c, kayo)
    r = c.post("/demandas", data={"title": "Relatório Aurora", "owner_id": str(bianca.id), "folder": "B",
                                  "requested_by": "Rafael", "due": "2026-10-20", "reserved": "on"}, follow_redirects=False)
    assert r.status_code == 303
    [d] = board(db, at(12))["todo"]
    assert (d.title, d.owner_id, d.folder, d.requested_by, d.due, d.reserved) == (
        "Relatório Aurora", bianca.id, "B", "Rafael", date(2026, 10, 20), True)
    assert "Relatório Aurora" in c.get("/?todas=1").text  # no app o título reservado aparece


def test_validation_keeps_typed_values(env):
    c, _, kayo, _ = env
    login(c, kayo)
    r = c.post("/demandas", data={"title": "", "owner_id": str(kayo.id), "requested_by": "Gerente Norte"})
    assert r.status_code == 422 and "Informe o título." in r.text and "Gerente Norte" in r.text


def test_move_flow(env):
    c, db, kayo, _ = env
    login(c, kayo)
    d = create_demand(db, at(8), kayo.id, title="Fluxo", owner_id=kayo.id)
    for col in ("doing", "done", "doing"):
        assert c.post(f"/demandas/{d.id}/mover", data={"column": col}, follow_redirects=False).status_code == 303
    assert [x.title for x in board(db, at(12))["doing"]] == ["Fluxo"]


def test_edit_and_delete(env):
    c, db, kayo, _ = env
    login(c, kayo)
    d = create_demand(db, at(8), kayo.id, title="Antes", owner_id=kayo.id)
    assert "Antes" in c.get(f"/demandas/{d.id}").text
    c.post(f"/demandas/{d.id}", data={"title": "Depois", "owner_id": str(kayo.id)})
    assert board(db, at(12))["todo"][0].title == "Depois"
    c.post(f"/demandas/{d.id}/excluir")
    assert board(db, at(12))["todo"] == []


def test_only_mine_filter(env):
    c, db, kayo, bianca = env
    login(c, kayo)
    create_demand(db, at(8), kayo.id, title="Minha", owner_id=kayo.id)
    create_demand(db, at(8), kayo.id, title="Do Bianca", owner_id=bianca.id)
    mine = c.get("/").text
    assert "Minha" in mine and "Do Bianca" not in mine
    assert "Do Bianca" in c.get("/?todas=1").text


def test_presence_button(env):
    c, db, kayo, _ = env
    login(c, kayo)
    c.post("/presenca", data={"status": "Em reunião"})
    assert [s for p, s, _ in presence_board(db, at(12)) if p.id == kayo.id] == ["Em reunião"]
    assert 'aria-pressed="true"' in c.get("/").text


def test_deactivated_cookie_goes_back_to_entrar(env):
    c, db, kayo, _ = env
    login(c, kayo)
    deactivate_person(db, at(9), None, kayo.id)
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/entrar"


def test_history_readable(env):
    c, db, kayo, _ = env
    login(c, kayo)
    d = create_demand(db, at(8), kayo.id, title="Plano Brisa", owner_id=kayo.id)
    c.post(f"/demandas/{d.id}/mover", data={"column": "doing"})
    html = c.get("/historico?de=2026-10-19&ate=2026-10-19").text
    assert "Kayo moveu" in html and "Plano Brisa" in html and "Fazendo" in html


def test_people_admin(env):
    c, db, kayo, _ = env
    login(c, kayo)
    c.post("/pessoas", data={"id": "", "name": "Helena", "initials": "", "color": ""})
    assert "Helena" in [p.name for p in list_people(db)]
    r = c.post("/pessoas", data={"id": "", "name": "Helena", "initials": "", "color": ""})
    assert r.status_code == 422 and "Já existe alguém com esse nome." in r.text


def test_partial_board(env):
    c, db, kayo, _ = env
    login(c, kayo)
    create_demand(db, at(8), kayo.id, title="Parcial", owner_id=kayo.id)
    html = c.get("/parcial/quadro").text
    assert "Parcial" in html and "<html" not in html


# ---------- achados da revisão final ----------

def test_name_with_apostrophe_is_not_inside_inline_js(env):
    c, db, kayo, _ = env
    login(c, kayo)
    add_person(db, at(9), None, "Pedro D'Ávila")
    html = c.get("/pessoas").text
    assert "data-nome=" in html and "confirm('Tirar Pedro" not in html


def test_partial_board_carries_fresh_presence(env):
    c, db, kayo, _ = env
    login(c, kayo)
    c.post("/presenca", data={"status": "Na sala"})
    html = c.get("/parcial/quadro").text
    assert 'aria-pressed="true"' in html and "Na sala" in html


def test_presence_from_yesterday_shows_out_in_app(db):
    from hub.presence import set_status
    kayo = add_person(db, at(7, day=18), None, "Kayo")
    set_status(db, at(9, day=18), kayo.id, "Na sala")
    c = TestClient(create_app(db, clock=lambda: at(8)), base_url=BASE)
    login(c, kayo)
    html = c.get("/parcial/quadro").text
    pressed = html.split('aria-pressed="true"')[1][:40]
    assert "Fora da empresa" in pressed


def test_editing_demand_of_deactivated_owner_keeps_owner(env):
    c, db, kayo, bianca = env
    login(c, kayo)
    d = create_demand(db, at(8), kayo.id, title="Do Bianca", owner_id=bianca.id)
    deactivate_person(db, at(9), None, bianca.id)
    form = c.get(f"/demandas/{d.id}").text
    assert f'value="{bianca.id}" selected' in form
    r = c.post(f"/demandas/{d.id}", data={"title": "Do Bianca (revisado)", "owner_id": str(bianca.id)},
               follow_redirects=False)
    assert r.status_code == 303
    assert board(db, at(12))["todo"][0].owner_id == bianca.id
