"""Servidor do Hub: a tela da TV e o app dos analistas."""

from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..db import Database
from ..demands import COLUMNS, board, tv_card
from ..people import list_people
from ..presence import presence_board

HERE = Path(__file__).parent


def create_app(db: Database, clock: Callable[[], datetime] = datetime.now) -> FastAPI:
    app = FastAPI(title="Hub dos Analistas", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")

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

    app.state.templates = templates
    return app
