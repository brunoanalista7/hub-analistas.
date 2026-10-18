// Quadro do analista: recarrega só o trecho do quadro a cada 10 s.
// Fica só nesta página: nos formulários nada se atualiza sozinho, para não apagar o que se digita.
(function () {
  "use strict";
  const quadro = document.getElementById("quadro");
  if (!quadro) return;
  setInterval(async () => {
    if (document.hidden) return;
    try {
      const r = await fetch(quadro.dataset.parcial, { cache: "no-store" });
      if (r.ok) quadro.innerHTML = await r.text();  // HTML do próprio servidor, já escapado pelo Jinja
    } catch (e) {
      // sem rede: mantém o que está na tela e tenta de novo no próximo ciclo
    }
  }, 10000);
})();
