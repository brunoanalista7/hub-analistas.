"""Servidor do Hub: a tela da TV e o app dos analistas."""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import __version__
from ..db import Database, events
from ..demands import (COLUMN_LABELS, COLUMNS, FOLDERS, board, create_demand, delete_demand, demand_titles,
                       find_demand, is_overdue, move_demand, tv_card, update_demand)
from ..people import (PALETTE, Person, ValidationError, add_person, deactivate_person, get_person, list_people,
                      update_person)
from ..presence import STATUSES, presence_board, set_status

HERE = Path(__file__).parent
COOKIE = "hub_pessoa"
COOKIE_DAYS = 365


def create_app(db: Database, clock: Callable[[], datetime] = datetime.now) -> FastAPI:
    app = FastAPI(title="Hub dos Analistas", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")
    # ?v=versão nos arquivos estáticos: a TV não fica presa a um CSS/JS antigo depois de atualizar
    templates.env.globals["version"] = __version__

    @app.middleware("http")
    async def same_origin_only(request: Request, call_next):
        # outro site aberto no navegador de alguém não pode mandar formulários para o Hub
        if request.method == "POST":
            source = request.headers.get("origin") or request.headers.get("referer")
            if source and urlsplit(source).netloc != request.headers.get("host"):
                return Response("Origem não permitida.", status_code=403)
        return await call_next(request)

    # ---------- TV ----------

    @app.get("/tv", response_class=HTMLResponse)
    def tv(request: Request):
        # só o esqueleto: os dados chegam pelo /api/tv, já sem nada de demanda reservada
        return templates.TemplateResponse(request, "tv.html", {})

    @app.get("/api/tv")
    def api_tv():
        now = clock()
        owners = {p.id: p for p in list_people(db, active_only=False)}
        columns = board(db, now)
        return {
            "now": now.isoformat(timespec="seconds"),
            "people": [
                {"name": p.name, "initials": p.initials, "color": p.color, "status": status,
                 "since": since.strftime("%H:%M")}
                for p, status, since in presence_board(db, now)
            ],
            "columns": {c: [tv_card(d, owners[d.owner_id], now.date()) for d in columns[c]] for c in COLUMNS},
            "counts": {c: len(columns[c]) for c in COLUMNS},
        }

    # ---------- app do analista ----------

    templates.env.globals.update(
        COLUMN_LABELS=COLUMN_LABELS, FOLDERS=FOLDERS, STATUSES=STATUSES, is_overdue=is_overdue,
    )

    def me(request: Request) -> Person | None:
        try:
            person = get_person(db, int(request.cookies.get(COOKIE, "")))
        except ValueError:
            return None
        return person if person and person.active else None

    def page(request: Request, name: str, user: Person | None, status_code: int = 200, **ctx) -> HTMLResponse:
        return templates.TemplateResponse(request, name, {"user": user, **ctx}, status_code=status_code)

    def to_login() -> RedirectResponse:
        return RedirectResponse("/entrar", status_code=303)

    def board_context(user: Person, show_all: bool) -> dict:
        now = clock()
        return {
            "columns": board(db, now, owner_id=None if show_all else user.id),
            "owners": {p.id: p for p in list_people(db, active_only=False)},
            "today": now.date(),
            "show_all": show_all,
        }

    @app.get("/entrar", response_class=HTMLResponse)
    def entrar(request: Request):
        return page(request, "entrar.html", me(request), people=list_people(db))

    @app.post("/entrar")
    def entrar_post(person_id: int = Form(...)):
        r = RedirectResponse("/", status_code=303)
        r.set_cookie(COOKIE, str(person_id), max_age=COOKIE_DAYS * 86400, httponly=True, samesite="lax")
        return r

    @app.post("/sair")
    def sair():
        r = to_login()
        r.delete_cookie(COOKIE)
        return r

    @app.get("/", response_class=HTMLResponse)
    def quadro(request: Request, todas: int = 0):
        user = me(request)
        if user is None:
            return to_login()
        status = next(s for p, s, _ in presence_board(db, clock()) if p.id == user.id)
        return page(request, "quadro.html", user, status=status, **board_context(user, bool(todas)))

    @app.get("/parcial/quadro", response_class=HTMLResponse)
    def quadro_parcial(request: Request, todas: int = 0):
        user = me(request)
        if user is None:
            return Response(status_code=401)
        return page(request, "_quadro.html", user, **board_context(user, bool(todas)))

    @app.post("/presenca")
    def presenca(request: Request, status: str = Form(...)):
        user = me(request)
        if user is None:
            return to_login()
        set_status(db, clock(), user.id, status)
        return RedirectResponse("/", status_code=303)

    def demand_form(request: Request, user: Person, values: dict, status_code: int = 200, **ctx) -> HTMLResponse:
        return page(request, "demanda.html", user, status_code, v=values, people=list_people(db), **ctx)

    def parse_demand(form) -> tuple[dict, dict]:
        values = {
            "title": form.get("title", ""), "owner_id": form.get("owner_id", ""), "folder": form.get("folder", ""),
            "requested_by": form.get("requested_by", ""), "due": form.get("due", ""), "reserved": "reserved" in form,
        }
        try:
            due = date.fromisoformat(values["due"]) if values["due"] else None
        except ValueError:
            raise ValidationError("Data inválida.")
        owner = int(values["owner_id"]) if values["owner_id"].isdigit() else 0
        fields = dict(title=values["title"], owner_id=owner, folder=values["folder"] or None,
                      requested_by=values["requested_by"] or None, due=due, reserved=values["reserved"])
        return values, fields

    @app.get("/demandas/nova", response_class=HTMLResponse)
    def demanda_nova(request: Request):
        user = me(request)
        if user is None:
            return to_login()
        return demand_form(request, user, {"id": "", "title": "", "owner_id": str(user.id), "folder": "",
                                           "requested_by": "", "due": "", "reserved": False})

    @app.post("/demandas")
    async def demanda_criar(request: Request):
        user = me(request)
        if user is None:
            return to_login()
        form = await request.form()
        values = {"id": ""}
        try:
            parsed, fields = parse_demand(form)
            values.update(parsed)
            create_demand(db, clock(), user.id, **fields)
        except ValidationError as exc:
            values.update({k: form.get(k, "") for k in ("title", "owner_id", "folder", "requested_by", "due")},
                          reserved="reserved" in form)
            return demand_form(request, user, values, 422, error=str(exc))
        return RedirectResponse("/", status_code=303)

    @app.get("/demandas/{demand_id}", response_class=HTMLResponse)
    def demanda_editar(request: Request, demand_id: int):
        user = me(request)
        if user is None:
            return to_login()
        d = find_demand(db, demand_id)
        if d is None:
            return RedirectResponse("/", status_code=303)
        return demand_form(request, user, {
            "id": d.id, "title": d.title, "owner_id": str(d.owner_id), "folder": d.folder or "",
            "requested_by": d.requested_by or "", "due": d.due.isoformat() if d.due else "", "reserved": d.reserved,
        })

    @app.post("/demandas/{demand_id}")
    async def demanda_salvar(request: Request, demand_id: int):
        user = me(request)
        if user is None:
            return to_login()
        form = await request.form()
        values = {"id": demand_id}
        try:
            parsed, fields = parse_demand(form)
            values.update(parsed)
            update_demand(db, clock(), user.id, demand_id, **fields)
        except ValidationError as exc:
            values.update({k: form.get(k, "") for k in ("title", "owner_id", "folder", "requested_by", "due")},
                          reserved="reserved" in form)
            return demand_form(request, user, values, 422, error=str(exc))
        return RedirectResponse("/", status_code=303)

    @app.post("/demandas/{demand_id}/mover")
    def demanda_mover(request: Request, demand_id: int, column: str = Form(...)):
        user = me(request)
        if user is None:
            return to_login()
        try:
            move_demand(db, clock(), user.id, demand_id, column)
        except ValidationError:
            pass  # outro PC já excluiu: o quadro atualizado mostra a verdade
        return RedirectResponse(request.headers.get("referer") or "/", status_code=303)

    @app.post("/demandas/{demand_id}/excluir")
    def demanda_excluir(request: Request, demand_id: int):
        user = me(request)
        if user is None:
            return to_login()
        try:
            delete_demand(db, clock(), user.id, demand_id)
        except ValidationError:
            pass
        return RedirectResponse("/", status_code=303)

    # ---------- histórico ----------

    @app.get("/historico", response_class=HTMLResponse)
    def historico(request: Request, de: str = "", ate: str = "", pessoa: str = ""):
        user = me(request)
        if user is None:
            return to_login()
        end = date.fromisoformat(ate) if ate else clock().date()
        start = date.fromisoformat(de) if de else end - timedelta(days=6)
        person_id = int(pessoa) if pessoa.isdigit() else None
        rows = events(db, start, end, person_id)
        people = {p.id: p for p in list_people(db, active_only=False)}
        titles = demand_titles(db)
        lines = [(datetime.fromisoformat(r["at"]), describe(r, people, titles)) for r in rows]
        return page(request, "historico.html", user, lines=lines, start=start, end=end, pessoa=pessoa,
                    people=list_people(db, active_only=False))

    # ---------- pessoas ----------

    @app.get("/pessoas", response_class=HTMLResponse)
    def pessoas(request: Request):
        user = me(request)
        if user is None and list_people(db):
            return to_login()
        return page(request, "pessoas.html", user, people=list_people(db), palette=PALETTE)

    @app.post("/pessoas")
    async def pessoas_salvar(request: Request):
        user = me(request)
        if user is None and list_people(db):
            return to_login()
        form = await request.form()
        actor = user.id if user else None
        try:
            if form.get("id"):
                update_person(db, clock(), actor, int(form["id"]), name=form.get("name", ""),
                              initials=form.get("initials", ""), color=form.get("color", ""))
            else:
                add_person(db, clock(), actor, form.get("name", ""), form.get("initials", ""), form.get("color", ""))
        except ValidationError as exc:
            return page(request, "pessoas.html", user, 422, people=list_people(db), palette=PALETTE, error=str(exc),
                        v={k: form.get(k, "") for k in ("id", "name", "initials", "color")})
        return RedirectResponse("/pessoas", status_code=303)

    @app.post("/pessoas/{person_id}/desativar")
    def pessoas_desativar(request: Request, person_id: int):
        user = me(request)
        if user is None:
            return to_login()
        deactivate_person(db, clock(), user.id, person_id)
        return RedirectResponse("/pessoas", status_code=303)

    app.state.templates = templates
    return app


def describe(row, people: dict, titles: dict) -> str:
    """Uma linha de histórico em português."""
    who = people[row["actor_id"]].name if row["actor_id"] in people else "Alguém"
    kind, subject, detail = row["kind"], row["subject"], row["detail"]
    ref_id = int(subject.split(":")[1]) if ":" in subject else 0
    title = titles.get(ref_id, detail) if subject.startswith("demanda:") else ""
    name = people[ref_id].name if subject.startswith("pessoa:") and ref_id in people else detail
    return {
        "demanda_criada": f"{who} criou “{title}”",
        "demanda_editada": f"{who} editou “{title}”",
        "demanda_movida": f"{who} moveu “{title}” para {COLUMN_LABELS.get(detail, detail)}",
        "demanda_excluida": f"{who} excluiu “{title}”",
        "presenca": f"{who} ficou: {detail}",
        "pessoa_criada": f"{who} cadastrou {name}",
        "pessoa_editada": f"{who} editou o cadastro de {name}",
        "pessoa_desativada": f"{who} desativou {name}",
    }.get(kind, f"{who}: {kind}")
