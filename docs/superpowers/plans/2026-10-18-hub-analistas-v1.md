# Hub dos Analistas v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Servidor local num PC da sala que mostra na TV a presença da equipe e o quadro de demandas (A fazer / Fazendo / Concluído hoje), alimentado pelos analistas pelo navegador dos próprios PCs.

**Architecture:** Um processo Python (FastAPI) no PC reserva guarda tudo num SQLite e serve duas faces: a página da TV (`/tv`, que busca `/api/tv` a cada 5 s com JavaScript simples) e o app do analista (páginas HTML com formulários). As regras do dia (o que é "Concluído hoje", quem voltou para "Fora da empresa", o que está atrasado) são **calculadas na hora a partir das datas**: não existe tarefa agendada de meia-noite que possa falhar. Toda mudança grava um evento no histórico.

**Tech Stack:** Python 3.12+, FastAPI + Uvicorn + Jinja2, sqlite3 (biblioteca padrão, modo WAL), JavaScript puro na TV (sem build), pytest + httpx.

**Spec:** `docs/superpowers/specs/2026-10-18-hub-analistas-v1-design.md`

## Global Constraints

- Python **3.12+**; Windows **sem administrador** (a única exceção possível é uma regra de firewall pedida à TI, Task 1).
- Servidor em `0.0.0.0`, porta **8800** (o Pombo usa 8765).
- Interface em **português**; identificadores em **inglês**; comentários e documentação em **português**.
- Pasta de dados: `%LOCALAPPDATA%\Hub` (sobrescrevível por `HUB_DADOS`, usada nos testes). Banco `hub.db` em **modo WAL**, `timeout=5`.
- Status de presença, exatamente: `Na sala`, `Em reunião`, `Pausa`, `Fora da empresa`. Escolhidos **só pela própria pessoa**.
- Colunas, no código `todo` | `doing` | `done`, na tela **A fazer**, **Fazendo**, **Concluído hoje**.
- Pastas: `A`, `B`, `C`, `D`, `E`, `F`, `G` (exibida "G (Canal Farma)").
- Campos da demanda: título (obrigatório, até 120 caracteres), dono (obrigatório), pasta, pedido por (até 60), prazo (data), **reservada** (sim/não).
- Demanda reservada: na TV, o texto é **"Demanda reservada"** + cor e iniciais do dono + prazo/atrasado. Título, pasta e "pedido por" **nunca saem do servidor para a TV**.
- "Concluído hoje" = `done_at` com a data de hoje (hora local). Presença marcada antes de hoje vale como **`Fora da empresa` desde 00:00 de hoje**.
- Ordem em A fazer e Fazendo: atrasados primeiro → prazo mais próximo (sem prazo por último) → mais antigos primeiro. Em Concluído hoje: concluídos mais recentes primeiro.
- TV: projetada para 1920×1080, título do cartão ≥ **28 px**, nome na faixa ≥ **32 px**, tema escuro; **nunca rola**; o que não cabe vira "+ N demandas"; atualização a cada **5 s**; sem resposta, mantém a última tela + "sem atualização desde HH:MM".
- App do analista: atualiza o quadro a cada **10 s**, sem perder o que se está digitando.
- Cópia de segurança diária do banco, últimos **14 dias**.
- Nenhum nome real da equipe no repositório (exemplos fictícios). Commits sem linhas de atribuição.

## Review Focus

1. **Vazamento de demanda reservada pela TV:** o título não pode aparecer em nenhum caminho da TV (JSON, HTML, atributo `title`, contagem com texto). *Teste na Task 4 e na Task 6.*
2. **Dois PCs mexendo no mesmo cartão ao mesmo tempo:** sem erro 500 e sem "database is locked" para o usuário; vale a última mudança e o histórico registra as duas. *Teste na Task 4.*
3. **Servidor caiu ou PC reserva reiniciou:** a TV continua mostrando a última tela, avisa "sem atualização desde" e volta sozinha. *Teste na Task 6 (JS verificado com servidor parado).*
4. **Virada do dia:** um cartão concluído às 23:59 some da TV à meia-noite, e quem marcou "Na sala" ontem aparece "Fora da empresa" hoje, sem tarefa agendada. *Teste nas Tasks 4 e 5.*
5. **Títulos longos e muitos cartões:** a TV nunca rola; o título passa de 2 linhas com reticências; a coluna termina em "+ N demandas". *Teste na Task 6.*

---

## Estrutura de arquivos

```
hub-analistas/
  hub/
    __init__.py
    __main__.py        # Task 8
    paths.py  db.py    # Task 2
    people.py          # Task 3
    demands.py         # Task 4
    presence.py        # Task 5
    backup.py          # Task 8
    winsys.py          # Task 8
    web/
      app.py           # Tasks 6, 7
      templates/       # tv.html, base.html, entrar.html, quadro.html, _quadro.html, demanda.html, historico.html, pessoas.html
      static/          # tv.css, tv.js, app.css, app.js
  tools/
    net_test.py        # Task 1
    seed_demo.py       # Task 9
  tests/
  docs/
  instalar.bat  iniciar.bat  requirements.txt  requirements-dev.txt  pyproject.toml  .gitignore  .gitattributes  README.md  LICENSE
```

---

### Task 1: Base do projeto + teste de rede no PC reserva

Primeiro risco (spec §10): o Firewall do Windows pode bloquear outros PCs de abrir o Hub.

**Files:** Create `pyproject.toml` (pytest com `pythonpath=["."]`), `requirements.txt`, `requirements-dev.txt` (mesmas versões fixas do Pombo: fastapi 0.145.0, uvicorn 0.54.0, Jinja2 3.1.6, python-multipart 0.0.32; dev: pytest 9.1.1, httpx 0.28.1), `.gitattributes` (`* text=auto eol=lf`, `*.bat text eol=crlf`, `*.cmd text eol=crlf`), `hub/__init__.py`, `tools/net_test.py`, `tests/test_smoke.py`, `docs/decisoes.md`, `LICENSE` (MIT).

- [ ] **Step 1:** `tests/test_smoke.py`: `def test_package_imports(): import hub`. Rodar `python -m pytest -q` → FAIL; criar `hub/__init__.py` → PASS.
- [ ] **Step 2:** `tools/net_test.py` (só biblioteca padrão): sobe `http.server` em `0.0.0.0:8800` respondendo "Hub: conexão OK", imprime o nome do PC (`socket.gethostname()`) e os IPs locais, e diz: "Abra http://<nome>:8800 em outro PC". Fica rodando até Ctrl+C.
- [ ] **Step 3 (manual, na empresa):** rodar no PC reserva; abrir o endereço em outro PC. Anotar: (a) abriu? (b) o Windows mostrou o aviso do firewall pedindo admin? Registrar em `docs/decisoes.md`. Se bloquear: pedir à TI uma regra de entrada para a porta 8800. Se a TI recusar, **parar e voltar ao Kayo** (o plano B muda a arquitetura).
- [ ] **Step 4:** Commit `chore: base do projeto e teste de rede`.

---

### Task 2: Banco de dados e histórico

**Files:** Create `hub/paths.py`, `hub/db.py` · Test `tests/test_db.py`

**Interfaces — Produces:**
- `paths.data_dir() -> Path` (`HUB_DADOS` ou `%LOCALAPPDATA%\Hub`, criada se faltar)
- `class Database(path: Path)`: `.connect() -> sqlite3.Connection` (context manager que faz commit ou rollback; `row_factory = sqlite3.Row`, `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `timeout=5`); `.init()` cria as tabelas se faltarem
- Tabelas:
  - `people(id INTEGER PK, name TEXT UNIQUE NOT NULL, initials TEXT NOT NULL, color TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1)`
  - `demands(id INTEGER PK, title TEXT NOT NULL, owner_id INTEGER NOT NULL REFERENCES people, folder TEXT, requested_by TEXT, due TEXT, reserved INTEGER NOT NULL DEFAULT 0, column_ TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, done_at TEXT, deleted INTEGER NOT NULL DEFAULT 0)`
  - `presence(person_id INTEGER PK REFERENCES people, status TEXT NOT NULL, since TEXT NOT NULL)`
  - `events(id INTEGER PK, at TEXT NOT NULL, actor_id INTEGER, kind TEXT NOT NULL, subject TEXT NOT NULL, detail TEXT NOT NULL)`
  - Datas em ISO local (`2026-10-19T10:15:00`)
- `log_event(conn, at: datetime, actor_id: int | None, kind: str, subject: str, detail: str) -> None`. `kind` ∈ `pessoa_criada | pessoa_editada | pessoa_desativada | demanda_criada | demanda_editada | demanda_movida | demanda_excluida | presenca`
- `events(db, start: date, end: date, person_id: int | None = None) -> list[sqlite3.Row]`: mais recentes primeiro; `person_id` filtra por quem fez **ou** pelo dono da demanda citada em `subject` (`demanda:<id>`)

- [ ] **Step 1: Testes**: `init` é idempotente (duas vezes sem erro); o arquivo fica em WAL (`PRAGMA journal_mode` → `wal`); `log_event` + `events` filtrando período e pessoa; erro dentro do `with db.connect()` faz rollback (nada gravado); `data_dir` respeita `HUB_DADOS`.
- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: banco de dados e histórico`.

---

### Task 3: Pessoas

**Files:** Create `hub/people.py` · Test `tests/test_people.py`

**Interfaces — Produces:**
- `@dataclass(frozen=True) Person(id: int, name: str, initials: str, color: str, active: bool)`
- `class ValidationError(ValueError)`, com a mensagem em português para a tela (definida aqui e usada por todos os módulos)
- `PALETTE: tuple[str, ...]`: 8 cores bem distintas sobre fundo escuro (hex), em ordem de uso
- `add_person(db, now, actor_id: int | None, name: str, initials: str = "", color: str = "") -> Person`: iniciais padrão = primeiras letras de até 2 palavras do nome, em maiúsculas; cor padrão = primeira da `PALETTE` ainda não usada por pessoa ativa
- `update_person(db, now, actor_id, person_id, *, name=None, initials=None, color=None) -> Person`
- `deactivate_person(db, now, actor_id, person_id) -> None`: a pessoa sai da TV e da lista de "Entrar"; demandas e histórico ficam
- `list_people(db, active_only: bool = True) -> list[Person]`, por nome · `get_person(db, person_id) -> Person | None`

- [ ] **Step 1: Testes**: iniciais padrão ("Ana Clara" → "MR", "Kayo" → "K"); cores padrão sem repetir entre ativos; nome vazio → `ValidationError("Informe o nome.")`; nome repetido → `ValidationError("Já existe alguém com esse nome.")`; iniciais com mais de 3 letras → erro; cor fora do formato `#RRGGBB` → erro; desativar tira da lista ativa e registra `pessoa_desativada`; cada operação grava evento.
- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** PASS → **Step 5:** Commit `feat: cadastro de pessoas`.

---

### Task 4: Demandas e quadro

**Files:** Create `hub/demands.py` · Test `tests/test_demands.py`

**Interfaces — Consumes:** `Database`, `log_event`, `Person`, `ValidationError`, `get_person`
**Produces:**
- `COLUMNS = ("todo", "doing", "done")`, `COLUMN_LABELS = {"todo": "A fazer", "doing": "Fazendo", "done": "Concluído hoje"}`, `FOLDERS = ("A","B","C","D","E","F","G")`, `RESERVED_TEXT = "Demanda reservada"`
- `@dataclass(frozen=True) Demand(id, title, owner_id, folder, requested_by, due: date | None, reserved: bool, column: str, created_at: datetime, updated_at: datetime, done_at: datetime | None)`
- `create_demand(db, now, actor_id, *, title, owner_id, folder=None, requested_by=None, due=None, reserved=False) -> Demand` (entra em `todo`)
- `update_demand(db, now, actor_id, demand_id, *, title, owner_id, folder, requested_by, due, reserved) -> Demand`
- `move_demand(db, now, actor_id, demand_id, column: str) -> Demand`: ir para `done` grava `done_at = now`; sair de `done` limpa `done_at`
- `delete_demand(db, now, actor_id, demand_id) -> None` (marca `deleted=1`)
- `is_overdue(d: Demand, today: date) -> bool`: `due < today` e não está em `done`
- `board(db, now, owner_id: int | None = None) -> dict[str, list[Demand]]`: ordem da Global Constraints; `done` só com `done_at` de hoje
- `tv_card(d: Demand, owner: Person, today: date) -> dict`: `{"id", "initials", "color", "title", "folder", "requested_by", "due", "overdue"}`; se `d.reserved`: `title = RESERVED_TEXT`, `folder = None`, `requested_by = None`, mais a chave `"reserved": True`
- Validação (`ValidationError`, mensagens exatas): título vazio → "Informe o título."; mais de 120 caracteres → "Título muito longo (máximo 120)."; dono inexistente ou inativo → "Escolha o dono da demanda."; pasta fora de `FOLDERS` → "Pasta inválida."; `requested_by` com mais de 60 caracteres → "\"Pedido por\" muito longo (máximo 60)."; coluna inválida → "Coluna inválida."; demanda inexistente ou excluída → "Demanda não encontrada."

- [ ] **Step 1: Testes**
```python
def test_board_order_overdue_then_due_then_oldest(db, people): ...
    # hoje 19/10: A (sem prazo, criada 08:00), B (prazo 25/10), C (prazo 17/10 = atrasada), D (prazo 20/10)
    # board(...)["todo"] -> [C, D, B, A]
def test_done_today_only_and_newest_first(db, people): ...
    # concluída ontem 23:59 não aparece hoje 00:00; duas de hoje -> a mais recente primeiro
def test_move_back_from_done_clears_done_at(db, people): ...
def test_events_record_actor_for_each_change(db, people): ...
    # criar (ator Kayo), mover (ator Bianca) -> 2 eventos com os atores certos e subject "demanda:<id>"
def test_reserved_tv_card_hides_everything_sensitive(db, people): ...   # Review Focus 1
    # reservada com title="Comissões RCA", folder="B", requested_by="Diretoria", due amanhã
    # card == {..., "title": "Demanda reservada", "folder": None, "requested_by": None, "due": amanhã, "reserved": True}
    # e "Comissões" not in json.dumps(card)
def test_concurrent_moves_do_not_fail(tmp_path, people): ...   # Review Focus 2
    # duas threads com Database próprio movendo o mesmo cartão 50 vezes cada -> nenhuma exceção; 100 eventos demanda_movida
def test_validation_messages(db, people): ...   # cada mensagem da lista acima
def test_deleted_disappears_from_board(db, people): ...
```
- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** PASS → **Step 5:** Commit `feat: demandas e quadro`.

---

### Task 5: Presença

**Files:** Create `hub/presence.py` · Test `tests/test_presence.py`

**Interfaces — Produces:**
- `STATUSES = ("Na sala", "Em reunião", "Pausa", "Fora da empresa")`, `DEFAULT = "Fora da empresa"`
- `set_status(db, now, person_id: int, status: str) -> None`: a própria pessoa é a autora (`actor_id = person_id`); status inválido → `ValidationError("Status inválido.")`; status igual ao atual não grava evento nem muda o "desde"
- `effective(status: str | None, since: datetime | None, now: datetime) -> tuple[str, datetime]`: sem registro, ou marcado antes de hoje → `(DEFAULT, 00:00 de hoje)`
- `presence_board(db, now) -> list[tuple[Person, str, datetime]]`: pessoas ativas por nome, com o status efetivo

- [ ] **Step 1: Testes**: sem registro → "Fora da empresa" desde 00:00; "Na sala" ontem 17:00 → hoje "Fora da empresa" desde 00:00 (Review Focus 4); marcar "Em reunião" às 10:15 → "desde 10:15"; marcar o mesmo status de novo não muda o "desde"; status inválido → erro; evento `presenca` gravado com o ator = a pessoa.
- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** PASS → **Step 5:** Commit `feat: presença`.

---

### Task 6: TV (`/api/tv` + página)

**Files:** Create `hub/web/__init__.py`, `hub/web/app.py`, `hub/web/templates/tv.html`, `hub/web/static/tv.css`, `hub/web/static/tv.js` · Test `tests/test_web_tv.py`

**Interfaces — Produces:**
- `create_app(db: Database, clock: Callable[[], datetime] = datetime.now) -> FastAPI`, com middleware de mesma origem: um POST com `Origin`/`Referer` cujo host:porta difere do `Host` da requisição → 403 "Origem não permitida."
- `GET /api/tv` → `{"now": iso, "people": [{"name", "initials", "color", "status", "since": "HH:MM"}], "columns": {"todo": [tv_card…], "doing": [...], "done": [...]}, "counts": {"todo": n, "doing": n, "done": n}}`
- `GET /tv` → página com CSS e JS próprios, sem dados embutidos (o JS busca `/api/tv`)
- `tv.js`: busca `/api/tv` a cada 5 s; monta a faixa e as colunas; em cada coluna, acrescenta cartões enquanto cabem e, se algum ficou de fora, troca o último pelo "+ N demandas" (medindo `scrollHeight` contra `clientHeight`); título limitado a 2 linhas com reticências (`-webkit-line-clamp: 2`); cartão atrasado com borda e rótulo "atrasada"; reservada em itálico com ícone de cadeado (SVG embutido); em falha de rede, mantém a tela e mostra "sem atualização desde HH:MM", e no próximo sucesso o aviso some; nunca usa `innerHTML` com texto vindo da API (usa `textContent`)

- [ ] **Step 1: Testes (TestClient)**: `/api/tv` com 2 pessoas e 4 demandas traz a ordem da Task 4 e as contagens; **reservada**: a resposta inteira (`r.text`) não contém o título, a pasta nem o "pedido por" (Review Focus 1); `/tv` não contém nenhum título de demanda (só o esqueleto); presença de ontem sai como "Fora da empresa"; POST com `Origin: http://outro:9999` → 403.
- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** PASS.
- [ ] **Step 5 (visual, no navegador):** `tools/seed_demo.py` (Task 9) ainda não existe; usar um banco montado no teste. Abrir `/tv` em 1920×1080 com 25 cartões e um título de 120 caracteres: a coluna termina em "+ N demandas", não há barra de rolagem e o título tem no máximo 2 linhas (Review Focus 5). Parar o servidor: aparece "sem atualização desde" e a tela continua; religar: o aviso some em até 5 s (Review Focus 3). Salvar o print em `docs/imagens/tv.png`.
- [ ] **Step 6:** Commit `feat: tela da TV`.

---

### Task 7: App do analista

**Files:** Modify `hub/web/app.py` · Create `templates/base.html`, `entrar.html`, `quadro.html`, `_quadro.html`, `demanda.html`, `historico.html`, `pessoas.html`, `static/app.css`, `static/app.js` · Test `tests/test_web_app.py`

**Interfaces — rotas** (todas as de escrita gravam o ator = pessoa do cookie `hub_pessoa`; sem cookie válido, ou de pessoa desativada → redireciona para `/entrar`):
- `GET /entrar` (lista de pessoas ativas como botões) · `POST /entrar` (`person_id`) → cookie `hub_pessoa` por 365 dias, `HttpOnly`, `SameSite=Lax` → 303 `/` · `POST /sair`
- `GET /` → presença (4 botões grandes, o atual destacado) + quadro (3 colunas) com filtro "Só as minhas" (padrão ligado; `?todas=1` desliga) + botão "Nova demanda"
- `GET /parcial/quadro` → só o trecho do quadro; `app.js` recarrega esse trecho a cada 10 s **apenas** na página do quadro, nunca nos formulários
- `POST /presenca` (`status`) → 303 `/`
- `GET /demandas/nova` · `POST /demandas` · `GET /demandas/{id}` (edição) · `POST /demandas/{id}` · `POST /demandas/{id}/mover` (`column`) · `POST /demandas/{id}/excluir` (com `confirm()` no botão)
- Botões por coluna: A fazer → "Começar"; Fazendo → "Concluir" e "Voltar"; Concluído hoje → "Reabrir" (volta para Fazendo)
- `GET /historico?de=&ate=&pessoa=` (padrão: últimos 7 dias): data/hora, quem, o que, em texto legível ("Kayo moveu 'Relatório X' para Fazendo"); demanda reservada aparece com o título **no app** (o app é dos analistas)
- `GET /pessoas` · `POST /pessoas` (nova/editar) · `POST /pessoas/{id}/desativar`
- Erros de validação: o formulário volta com status 422, a mensagem e o que foi digitado

- [ ] **Step 1: Testes**: sem cookie → `/` redireciona para `/entrar`; entrar define o cookie; criar demanda grava com ator e dono; título vazio → 422 com "Informe o título." e o resto preservado; mover/concluir/reabrir; excluir; "Só as minhas" mostra só as do usuário e `?todas=1` mostra todas; presença muda e aparece destacada; cookie de pessoa desativada → `/entrar`; histórico com frase legível; cadastro de pessoa com cor e iniciais padrão.
- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** PASS → **Step 5:** Commit `feat: app do analista`.

---

### Task 8: Inicialização, backup e instalação

**Files:** Create `hub/__main__.py`, `hub/backup.py`, `hub/winsys.py`, `instalar.bat`, `iniciar.bat` · Test `tests/test_backup.py`, `tests/test_main.py`

**Interfaces — Produces:**
- `backup.make_backup(db_path: Path, dest: Path, today: date, keep: int = 14) -> Path`: `sqlite3` `.backup()` para `dest/hub-AAAA-MM-DD.db` (sobrescreve o do mesmo dia) e apaga os mais antigos além de `keep`
- `__main__.acquire_port(port=8800) -> socket | None` (bind em `0.0.0.0` com `SO_EXCLUSIVEADDRUSE` no Windows) · `server_config(app)` com `log_config=None` (roda sob `pythonw`, sem console; lição do Pombo) · `main()`: segunda instância só abre a TV e sai; senão `keep_awake()`, `Database.init()`, backup ao iniciar e a cada 24 h numa thread, Uvicorn com o socket
- `winsys.keep_awake()` e `winsys.set_start_with_windows(enabled, project_dir)` (iguais ao Pombo, arquivo `Hub.cmd` na pasta Inicializar, em página de código OEM) · `winsys.open_tv(url)`: `start "" msedge --kiosk <url> --edge-kiosk-type=fullscreen --no-first-run`
- `iniciar.bat`: `start "" .venv\Scripts\pythonw.exe -m hub`, espera 3 s e abre a TV em quiosque · `instalar.bat`: igual ao do Pombo

- [ ] **Step 1: Testes**: backup cria o arquivo do dia, legível com `sqlite3`, e mantém só 14; `acquire_port` devolve `None` com a porta ocupada; `server_config` funciona com `sys.stdout = None` e `sys.stderr = None`; segunda instância não cria `Database` (monkeypatch).
- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** PASS.
- [ ] **Step 5 (manual):** `iniciar.bat` sob `pythonw`: o servidor responde em `http://127.0.0.1:8800/tv`; abrir de novo não cria um segundo processo.
- [ ] **Step 6:** Commit `feat: inicialização, backup e instalação`.

---

### Task 9: Demonstração e documentação

**Files:** Create `tools/seed_demo.py`, `README.md`, `docs/instalacao.md`, `docs/primeiro-uso.md`, `docs/arquitetura.md`, `docs/seguranca-e-dados.md`, `docs/limitacoes.md`, `docs/roadmap.md`, `docs/imagens/` · Test `tests/test_seed_demo.py`

- `seed_demo.seed()`: exige `HUB_DADOS` e se recusa a escrever sobre um banco com pessoas (lição do Pombo). Cria 5 pessoas **fictícias** (ex.: "Ana Souza", "Bianca Lima", "Carla Dias", "Diego Rocha", "Elisa Prado") e cerca de 15 demandas variadas (com e sem prazo, uma atrasada, duas reservadas, concluídas hoje) e presenças variadas.
- Documentação: README com o print da TV e a ideia em uma frase; instalação no PC reserva (inclui o modo quiosque e o endereço para os analistas); primeiro uso (o teste de rede da Task 1); arquitetura (diagrama da spec §4 + "regras do dia calculadas, não agendadas"); segurança e dados (presença só pela própria pessoa, demanda reservada, nada sai da rede da empresa, sem senha na v1 e por quê); limitações; roadmap (spec §11).
- [ ] **Step 1: Testes**: recusa sem `HUB_DADOS`; recusa sobre banco com pessoas; pasta vazia → 5 pessoas e pelo menos 1 reservada.
- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** PASS.
- [ ] **Step 5:** Prints da TV e do app com os dados de demonstração em `docs/imagens/`. Varredura: `git grep -n -i` com os nomes reais da equipe, digitados na hora e nunca salvos em arquivo, deve voltar vazia.
- [ ] **Step 6:** Commit `docs: documentação do Hub`.

---

### Task 10: Aceite na empresa (manual)

- [ ] **Step 1:** Teste de rede da Task 1 no PC reserva (se ainda não foi feito).
- [ ] **Step 2:** Instalar no PC reserva pelo README, cadastrar a equipe real, ligar "Abrir com o Windows" e conferir a TV em quiosque.
- [ ] **Step 3:** Dois analistas, em PCs diferentes, lançam e movem demandas ao mesmo tempo: a TV mostra em até 5 s.
- [ ] **Step 4:** Uma demanda reservada não mostra o título na TV.
- [ ] **Step 5:** Reiniciar o PC reserva: o Hub e a TV voltam sozinhos.
- [ ] **Step 6:** Apresentar ao Rafael.
