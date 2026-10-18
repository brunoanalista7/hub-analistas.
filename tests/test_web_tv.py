from datetime import date

import pytest
from fastapi.testclient import TestClient

from conftest import at
from hub.demands import create_demand, move_demand
from hub.people import add_person
from hub.presence import set_status
from hub.web.app import create_app


@pytest.fixture
def setup(db):
    kayo = add_person(db, at(7), None, "Kayo")
    bianca = add_person(db, at(7), None, "Bianca")
    clock = {"now": at(12)}
    client = TestClient(create_app(db, clock=lambda: clock["now"]), base_url="http://hub-sala:8800")
    return client, db, kayo, bianca, clock


def test_api_tv_shape_order_and_counts(setup):
    c, db, kayo, bianca, _ = setup
    create_demand(db, at(8), kayo.id, title="Sem prazo", owner_id=kayo.id)
    create_demand(db, at(9), kayo.id, title="Atrasada", owner_id=bianca.id, due=date(2026, 10, 17))
    d = create_demand(db, at(10), kayo.id, title="Feita", owner_id=kayo.id)
    move_demand(db, at(11), kayo.id, d.id, "done")
    set_status(db, at(10, 15), kayo.id, "Em reunião")
    data = c.get("/api/tv").json()
    assert [x["title"] for x in data["columns"]["todo"]] == ["Atrasada", "Sem prazo"]
    assert data["counts"] == {"todo": 2, "doing": 0, "done": 1}
    assert data["columns"]["todo"][0]["overdue"] is True
    people = {p["name"]: p for p in data["people"]}
    assert people["Kayo"]["status"] == "Em reunião" and people["Kayo"]["since"] == "10:15"
    assert people["Bianca"]["status"] == "Fora da empresa"


def test_reserved_never_leaves_the_server(setup):
    # Review Focus 1
    c, db, kayo, _, _ = setup
    create_demand(db, at(8), kayo.id, title="Comissões RCA", owner_id=kayo.id, folder="B",
                  requested_by="Diretoria", reserved=True)
    body = c.get("/api/tv").text
    assert "Comissões" not in body and "Diretoria" not in body and "Demanda reservada" in body
    assert "Comissões" not in c.get("/tv").text


def test_tv_page_is_a_shell(setup):
    c, db, kayo, _, _ = setup
    create_demand(db, at(8), kayo.id, title="Relatório Aurora", owner_id=kayo.id)
    html = c.get("/tv").text
    assert "Relatório Aurora" not in html and "/static/tv.js" in html


def test_yesterday_presence_is_out_today(setup):
    c, db, kayo, _, clock = setup
    set_status(db, at(17, day=18), kayo.id, "Na sala")
    people = {p["name"]: p for p in c.get("/api/tv").json()["people"]}
    assert people["Kayo"]["status"] == "Fora da empresa"


def test_cross_origin_post_rejected(setup):
    c, *_ = setup
    r = c.post("/presenca", data={"status": "Na sala"}, headers={"Origin": "http://outro-site:9999"})
    assert r.status_code == 403
