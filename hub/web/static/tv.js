// TV da sala: busca o estado a cada 5 s e redesenha. Nunca rola: o que não cabe vira "+ N demandas".
// Todo texto vindo do servidor entra por textContent (nunca innerHTML).
(function () {
  "use strict";
  const INTERVALO_MS = 5000;
  const DIAS = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];
  const CLASSE_STATUS = { "Na sala": "st-sala", "Em reunião": "st-reuniao", "Pausa": "st-pausa", "Fora da empresa": "st-fora" };
  const CADEADO = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-1V7a5 5 0 0 0-5-5zm-3 8V7a3 3 0 0 1 6 0v3z"/></svg>';
  let ultimaAtualizacao = null;

  function el(tag, cls, texto) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (texto !== undefined) e.textContent = texto;
    return e;
  }

  function dataCurta(iso) {  // "2026-10-20" -> "20/10"
    return iso.slice(8, 10) + "/" + iso.slice(5, 7);
  }

  function relogio() {
    const agora = new Date();
    document.getElementById("data").textContent =
      DIAS[agora.getDay()] + ", " + String(agora.getDate()).padStart(2, "0") + "/" + String(agora.getMonth() + 1).padStart(2, "0");
    document.getElementById("hora").textContent =
      String(agora.getHours()).padStart(2, "0") + ":" + String(agora.getMinutes()).padStart(2, "0");
  }

  function desenharPresenca(pessoas) {
    const faixa = document.getElementById("presenca");
    faixa.replaceChildren();
    for (const p of pessoas) {
      const card = el("div", "pessoa " + (CLASSE_STATUS[p.status] || "st-fora"));
      card.style.setProperty("--cor", p.color);
      card.append(el("div", "ini", p.initials), el("div", "nome", p.name));
      const st = el("div", "status");
      st.append(el("b", "", p.status), el("span", "", "desde " + p.since));
      card.append(st);
      faixa.append(card);
    }
  }

  function cartao(c) {
    const card = el("div", "cartao" + (c.reserved ? " reservada" : "") + (c.overdue ? " atrasada" : ""));
    card.style.setProperty("--cor", c.color);
    card.append(el("div", "ini", c.initials));
    const titulo = el("div", "titulo");
    if (c.reserved) titulo.innerHTML = CADEADO;  // só o ícone fixo; o texto entra abaixo por textContent
    titulo.append(document.createTextNode(c.title));
    card.append(titulo);
    const meta = el("div", "meta");
    if (c.folder) meta.append(el("span", "", "Pasta " + (c.folder === "G" ? "G (Canal Farma)" : c.folder)));
    if (c.requested_by) meta.append(el("span", "", "Pedido por " + c.requested_by));
    if (c.overdue) meta.append(el("span", "atraso", "atrasada · prazo " + dataCurta(c.due)));
    else if (c.due) meta.append(el("span", "", "prazo " + dataCurta(c.due)));
    if (meta.childElementCount) card.append(meta);
    return card;
  }

  function encaixar(caixa, cartoes) {
    // acrescenta enquanto cabe; o que sobrar vira "+ N demandas"
    caixa.replaceChildren();
    if (!cartoes.length) { caixa.append(el("div", "vazio", "Nada aqui.")); return; }
    const cabe = () => caixa.scrollHeight <= caixa.clientHeight;
    let mostrados = 0;
    for (const c of cartoes) {
      caixa.append(cartao(c));
      if (!cabe()) { caixa.lastChild.remove(); break; }
      mostrados++;
    }
    if (mostrados === cartoes.length) return;
    const mais = el("div", "mais");
    caixa.append(mais);
    while (true) {
      mais.textContent = "+ " + (cartoes.length - mostrados) + (cartoes.length - mostrados === 1 ? " demanda" : " demandas");
      if (cabe() || mostrados === 0) break;
      mais.previousSibling.remove();
      mostrados--;
    }
  }

  function desenharQuadro(dados) {
    for (const sec of document.querySelectorAll(".coluna")) {
      const col = sec.dataset.col;
      sec.querySelector(".contagem").textContent = dados.counts[col];
      encaixar(sec.querySelector(".cartoes"), dados.columns[col]);
    }
  }

  function semConexao() {
    const aviso = document.getElementById("sem-conexao");
    const quando = ultimaAtualizacao
      ? String(ultimaAtualizacao.getHours()).padStart(2, "0") + ":" + String(ultimaAtualizacao.getMinutes()).padStart(2, "0")
      : "--:--";
    aviso.textContent = "Sem atualização desde " + quando;
    aviso.hidden = false;
  }

  let ultimoEstado = null;

  async function atualizar() {
    relogio();
    try {
      // servidor travado (aceita a conexão mas não responde) também conta como "sem atualização"
      const r = await fetch("/api/tv", { cache: "no-store", signal: AbortSignal.timeout(4000) });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const dados = await r.json();
      ultimaAtualizacao = new Date();
      document.getElementById("sem-conexao").hidden = true;
      ultimoEstado = dados;
      desenharPresenca(dados.people);
      desenharQuadro(dados);
    } catch (e) {
      semConexao();  // mantém a última tela
    }
  }

  // a TV pode mudar de tamanho (quiosque abrindo): reencaixa com o último estado
  window.addEventListener("resize", () => { if (ultimoEstado) desenharQuadro(ultimoEstado); });
  atualizar();
  setInterval(atualizar, INTERVALO_MS);
})();
