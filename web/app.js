// Filtro de Promessas — interface. Toda conta pesada (percentis, notas, validação) vem pronta do
// pipeline Python em data/wr.js; aqui só se escolhe o que mostrar. Assim a regra de negócio vive num
// lugar só e o HTML não pode divergir do que a memória reporta.
"use strict";

const D = window.DADOS;
const M = D.meta;
const PESOS = M.pesos_atleticos;
const BASE = PESOS.indexOf(M.peso_base);
const IND = D.indicadores;
const porId = new Map(D.jogadores.map((j) => [j.id, j]));
const [REF_INI, REF_FIM] = M.janela_referencia;
const GRUPO = `WRs draftados de ${REF_INI} a ${REF_FIM}`;
const anos = [...new Set(D.jogadores.map((j) => j.ano))].sort((a, b) => b - a);

const estado = { tela: "ranking", peso: BASE, ano: anos[0], jogador: null, eixoY: "jardas" };

// ---------- utilidades ----------
const $ = (sel, raiz = document) => raiz.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmt = (x, casas = 0) => (x == null ? "—" : x.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas }));
const pctTxt = (p) => (p == null ? "—" : `${Math.round(p)}`);
const pesoTxt = (k) => `${Math.round(PESOS[k] * 100)}%`;
const SVGNS = "http://www.w3.org/2000/svg";
function svg(tag, attrs = {}, filhos = []) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) el.setAttribute(k, v);
  for (const f of [].concat(filhos)) el.append(f);
  return el;
}
function quantil(ordenado, q) {
  if (!ordenado.length) return null;
  const pos = (ordenado.length - 1) * q, lo = Math.floor(pos), hi = Math.ceil(pos);
  return ordenado[lo] + (ordenado[hi] - ordenado[lo]) * (pos - lo);
}

const ROTULO_STATUS = {
  medido: "medido",
  pro_day_2021: "Pro Day (2021)",
  nao_testou: "não testou",
  sem_combine: "não testou (não foi ao Combine)",
  altura_listada: "listada pela CFBD",
  sem_dados_cfbd: "sem dado universitário",
  ultimo_ano_anterior: "último ano anterior",
  nao_atingiu: `não atingiu ${Math.round(M.limiar_breakout * 100)}%`,
  sem_dado: "sem dado",
};
const ROTULO_CURTO = { altura: "Altura", vertical: "Vertical", speed_score: "Speed Score", fatia_jardas: "Fatia das jardas",
  breakout_idade: "Breakout", idade_draft: "Idade no Draft" };
const AUSENTE = new Set(["nao_testou", "sem_combine", "sem_dados_cfbd", "sem_dado"]);
const ausentes = (j) => IND.filter((i) => AUSENTE.has(j.status[i.id]));

function fmtValor(ind, v, j) {
  if (j && j.status[ind.id] === "nao_atingiu") return "não atingiu";
  if (v == null) return "—";
  if (ind.id === "altura") return `${Math.floor(v / 12)}'${Math.round(v % 12)}" (${fmt(v * 2.54)} cm)`;
  if (ind.id === "fatia_jardas") return `${fmt(v * 100, 1)}%`;
  if (ind.id === "speed_score") return fmt(v, 1);
  if (ind.id === "vertical") return `${fmt(v, 1)} pol`;
  return `${fmt(v)} anos`;
}

// ---------- dica (tooltip) ----------
const dica = $("#dica");
function mostrarDica(ev, html) {
  dica.innerHTML = html;
  dica.hidden = false;
  const x = Math.min(ev.clientX + 12, window.innerWidth - dica.offsetWidth - 8);
  const y = ev.clientY + 14 + dica.offsetHeight > window.innerHeight ? ev.clientY - dica.offsetHeight - 10 : ev.clientY + 14;
  dica.style.left = `${Math.max(8, x)}px`;
  dica.style.top = `${y}px`;
}
const esconderDica = () => { dica.hidden = true; };

// ---------- controles globais ----------
const CENARIOS = [
  { k: PESOS.indexOf(0), nome: "Só produção" },
  { k: BASE, nome: "Base" },
  { k: PESOS.indexOf(0.4), nome: "Atlético" },
];
function top10(ano, k) {
  return D.jogadores.filter((j) => j.ano === ano && j.nota[k] != null).sort((a, b) => b.nota[k] - a.nota[k]).slice(0, 10).map((j) => j.id);
}
function mudancasTop10(ano, k) {
  const base = new Set(top10(ano, BASE));
  return top10(ano, k).filter((id) => !base.has(id)).length;
}
function desenharControles() {
  $("#peso").value = estado.peso;
  $("#peso-valor").textContent = `${pesoTxt(estado.peso)} atlético · ${Math.round((1 - PESOS[estado.peso]) * 100)}% produção`;
  $("#cenarios").innerHTML = CENARIOS.map((c) => {
    const n = mudancasTop10(estado.ano, c.k);
    const extra = c.k === BASE ? "" : ` <small>${n} mudam no top 10</small>`;
    return `<button type="button" data-k="${c.k}" aria-pressed="${c.k === estado.peso}">${c.nome} (${pesoTxt(c.k)})${extra}</button>`;
  }).join("");
}
$("#peso").addEventListener("input", (e) => { estado.peso = +e.target.value; render(); });
$("#cenarios").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (b) { estado.peso = +b.dataset.k; render(); }
});

// ---------- navegação ----------
document.querySelectorAll("nav.abas button").forEach((b) => b.addEventListener("click", () => irPara(b.dataset.tela)));
function irPara(tela, jogador) {
  estado.tela = tela;
  if (jogador) estado.jogador = jogador;
  history.replaceState(null, "", `#${tela}${tela === "perfil" && estado.jogador ? "=" + estado.jogador : ""}`);
  render();
  window.scrollTo({ top: 0 });
}
function lerEndereco() {
  const [tela, id] = location.hash.slice(1).split("=");
  if (["ranking", "perfil", "validacao", "metodologia"].includes(tela)) estado.tela = tela;
  if (id && porId.has(id)) { estado.jogador = id; estado.ano = porId.get(id).ano; }
}

// ---------- tela: ranking ----------
function renderRanking() {
  const el = $("#ranking");
  const k = estado.peso;
  const lista = D.jogadores.filter((j) => j.ano === estado.ano && j.nota[k] != null).sort((a, b) => b.nota[k] - a.nota[k]);
  const recente = estado.ano > REF_FIM;
  el.innerHTML = `
    <h2>Ranking da classe de ${estado.ano}</h2>
    <p class="lead">Percentil composto entre ${GRUPO} (o grupo de comparação). Percentil 70 quer dizer que a combinação
      de perfil atlético e produção universitária supera a de 70% desse grupo. É posição relativa, não previsão de carreira.</p>
    <div class="controles">
      <div class="controle"><label for="ano">Classe do Draft</label>
        <select id="ano">${anos.map((a) => `<option ${a === estado.ano ? "selected" : ""}>${a}</option>`).join("")}</select></div>
    </div>
    ${estado.ano === 2021 ? `<div class="aviso">2021 não teve Combine presencial. Os testes desta classe vêm, provavelmente, de Pro Days, que costumam registrar tempos mais rápidos; compare com cautela.</div>` : ""}
    ${recente ? `<div class="aviso">Classe sem 3 temporadas completas na NFL: aqui só dá para comparar a nota com o pick real (aba Validação).</div>` : ""}
    <div class="legenda" aria-hidden="true">
      <span><i style="background:var(--series-1)"></i>percentil composto</span>
      <span><i style="background:var(--banda)"></i>faixa possível se os testes não realizados tivessem qualquer resultado</span>
      <span><i style="background:var(--axis);width:2px;height:12px"></i>mediana do grupo (50)</span>
    </div>
    <ol class="lista-ranking">${lista.map((j, i) => linhaRanking(j, i, k)).join("")}</ol>
    <p class="nota-rodape">Clique num jogador para ver o perfil. Pick real e universidade aparecem abaixo do nome.
      ${lista.length} WRs draftados em ${estado.ano}.</p>`;
  $("#ano", el).addEventListener("change", (e) => { estado.ano = +e.target.value; render(); });
  el.querySelectorAll("button.linha").forEach((b) => b.addEventListener("click", () => irPara("perfil", b.dataset.id)));
}
function linhaRanking(j, i, k) {
  const [lo, hi] = j.faixa[k];
  const falta = ausentes(j).filter((ind) => ind.grupo === "producao" || PESOS[k] > 0);
  const etiqueta = falta.length ? `<span class="etiqueta">${falta.length} ${falta.length > 1 ? "indicadores" : "indicador"} sem dado</span>` : "";
  const faixa = hi - lo >= 1 ? `, faixa ${pctTxt(lo)} a ${pctTxt(hi)}` : "";
  return `<li><button type="button" class="linha" data-id="${j.id}"
      aria-label="${esc(j.nome)}: percentil ${pctTxt(j.nota[k])}${faixa}; pick ${j.pick}">
    <span class="pos tnum">${i + 1}</span>
    <span class="quem"><strong>${esc(j.nome)}${etiqueta}</strong><span>pick ${j.pick} · ${esc(j.universidade)}</span></span>
    <span class="trilho" aria-hidden="true">
      <span class="banda" style="left:${lo}%;width:${Math.max(0, hi - lo)}%"></span>
      <span class="barra" style="width:${j.nota[k]}%"></span>
      <span class="mediana"></span>
    </span>
    <span class="valor tnum">${pctTxt(j.nota[k])}</span>
  </button></li>`;
}

// ---------- tela: perfil ----------
function vizinhos(j, k, raio = 5) {
  const viz = D.jogadores.filter((o) => o.id !== j.id && o.ano >= REF_INI && o.ano <= REF_FIM && o.desfecho && o.nota[k] != null
    && Math.abs(o.nota[k] - j.nota[k]) <= raio);
  const jardas = viz.map((o) => o.desfecho.jardas).sort((a, b) => a - b);
  return { n: viz.length, q1: quantil(jardas, 0.25), med: quantil(jardas, 0.5), q3: quantil(jardas, 0.75),
    acima: viz.length ? jardas.filter((x) => x >= 2000).length / viz.length : null };
}
function renderPerfil() {
  const el = $("#perfil");
  if (!estado.jogador) {
    estado.jogador = D.jogadores.filter((j) => j.ano === estado.ano).sort((a, b) => b.nota[estado.peso] - a.nota[estado.peso])[0].id;
  }
  const j = porId.get(estado.jogador);
  const k = estado.peso;
  const [lo, hi] = j.faixa[k];
  const v = vizinhos(j, k);
  const falta = ausentes(j);
  el.innerHTML = `
    <div class="controles">
      <div class="controle"><label for="busca">Jogador (WRs draftados de ${anos.at(-1)} a ${anos[0]})</label>
        <input type="search" id="busca" list="lista-jogadores" placeholder="Digite um nome" autocomplete="off">
        <datalist id="lista-jogadores">${D.jogadores.map((o) => `<option value="${esc(o.nome)} (${o.ano})"></option>`).join("")}</datalist></div>
    </div>
    <h2>${esc(j.nome)}</h2>
    <p class="lead">Draft ${j.ano}, rodada ${j.rodada}, pick ${j.pick} (${esc(j.time_nfl)}) · ${esc(j.universidade)}${j.conferencia ? " · " + esc(j.conferencia) : ""}
      ${j.ranking_pre_draft ? ` · ranking pré-Draft da CFBD: ${j.ranking_pre_draft}º` : ""}</p>
    ${j.avisos.map((a) => `<div class="aviso">${esc(a)}</div>`).join("")}
    ${falta.length ? `<div class="aviso">${falta.length > 1 ? "Indicadores" : "Indicador"} sem dado: ${falta.map((i) => i.nome.toLowerCase()).join(", ")}.
      A nota usa só o que foi medido; a faixa mostra o que ela seria se o dado existisse com qualquer valor.</div>` : ""}
    <div class="perfil-grade">
      <div class="cartao radar">
        <p class="grafico titulo" style="margin:0">Percentis entre ${GRUPO}</p>
        <p class="nota-rodape" style="margin:0 0 4px">Para fora = melhor em todos os eixos (idades invertidas). Anel tracejado = mediana do grupo.</p>
        <div id="radar"></div>
      </div>
      <div>
        <div class="cartao">
          <div class="nota-rodape">Percentil composto com ${pesoTxt(k)} de peso atlético</div>
          <div class="destaque-numero tnum">${pctTxt(j.nota[k])}</div>
          <div class="faixa-texto">${hi - lo >= 1 ? `Faixa possível: ${pctTxt(lo)} a ${pctTxt(hi)}, conforme o resultado dos testes não realizados.` : "Todos os indicadores usados nesta nota foram medidos."}</div>
          <p style="margin:12px 0 0">${textoVizinhos(v)}</p>
          ${j.desfecho ? `<p style="margin:8px 0 0"><strong>O que aconteceu:</strong> ${fmt(j.desfecho.jardas)} jardas em ${j.desfecho.jogos} jogos nas 3 primeiras temporadas
            (${fmt(j.desfecho.alvos)} alvos${j.desfecho.jardas_por_alvo != null ? `, ${fmt(j.desfecho.jardas_por_alvo, 1)} jardas por alvo` : ""}).</p>`
            : j.ano <= REF_FIM ? `<p class="nota-rodape">Sem gsis_id na base: desfecho na NFL indisponível.</p>`
            : `<p class="nota-rodape">Ainda sem 3 temporadas completas na NFL.</p>`}
        </div>
        <div class="cartao tabela-rolagem">
          <table>
            <thead><tr><th>Indicador</th><th>Valor</th><th class="num">Percentil</th><th>Situação</th></tr></thead>
            <tbody>${IND.map((ind) => `<tr>
              <td>${ind.nome}<br><span class="nota-rodape">${ind.grupo === "atletico" ? "atlético" : "produção"} · ${ind.origem.toLowerCase()}</span></td>
              <td class="${AUSENTE.has(j.status[ind.id]) ? "ausente" : ""}">${AUSENTE.has(j.status[ind.id]) ? (j.status[ind.id] === "sem_dados_cfbd" ? "sem dado" : "não testou") : fmtValor(ind, j.valores[ind.id], j)}</td>
              <td class="num">${pctTxt(j.pct[ind.id])}</td>
              <td>${detalheStatus(j, ind)}</td></tr>`).join("")}</tbody>
          </table>
        </div>
      </div>
    </div>`;
  $("#radar").append(radar(j));
  const busca = $("#busca", el);
  busca.addEventListener("change", () => {
    const m = busca.value.match(/^(.*) \((\d{4})\)$/);
    const achado = m && D.jogadores.find((o) => o.nome === m[1] && o.ano === +m[2]);
    if (achado) { estado.ano = achado.ano; irPara("perfil", achado.id); }
  });
}
function textoVizinhos(v) {
  if (v.n < 10) return `Poucos WRs do grupo têm nota parecida (${v.n}); comparação com a produção na NFL não é informativa.`;
  return `<strong>Perfil semelhante:</strong> entre os ${v.n} ${GRUPO} com percentil composto a até 5 pontos deste,
    metade fez entre ${fmt(v.q1)} e ${fmt(v.q3)} jardas nas 3 primeiras temporadas (mediana ${fmt(v.med)}), e
    ${Math.round(v.acima * 100)}% passaram de 2.000 jardas. A variação é grande: a nota sozinha não define a carreira.`;
}
function detalheStatus(j, ind) {
  const s = j.status[ind.id];
  if (s === "ultimo_ano_anterior") return `último ano com estatística: ${j.fatia_temporada}`;
  if (s === "medido" && ind.id === "breakout_idade") return `breakout em ${j.breakout_temporada}`;
  if (s === "medido" && ind.id === "fatia_jardas") return `temporada ${j.fatia_temporada}`;
  if (s === "nao_atingiu") return `nenhuma temporada com ${Math.round(M.limiar_breakout * 100)}% das jardas do time (percentil baixo, não dado faltante)`;
  return ROTULO_STATUS[s] ?? s;
}
function radar(j) {
  const T = 360, c = T / 2, R = 112, n = IND.length, folga = 56;
  const ang = (i) => -Math.PI / 2 + (2 * Math.PI * i) / n;
  const pt = (i, p) => [c + Math.cos(ang(i)) * R * (p / 100), c + Math.sin(ang(i)) * R * (p / 100)];
  const s = svg("svg", { viewBox: `${-folga} 0 ${T + 2 * folga} ${T}`, role: "img",
    "aria-label": `Radar de percentis de ${j.nome}: ` + IND.map((i) => `${i.nome} ${AUSENTE.has(j.status[i.id]) ? "não testou" : pctTxt(j.pct[i.id])}`).join(", ") });
  for (const p of [25, 75, 100]) s.append(svg("polygon", { points: IND.map((_, i) => pt(i, p).join(",")).join(" "), fill: "none", stroke: "var(--grid)" }));
  s.append(svg("polygon", { points: IND.map((_, i) => pt(i, 50).join(",")).join(" "), fill: "none", stroke: "var(--axis)", "stroke-dasharray": "3 3" }));
  IND.forEach((ind, i) => {
    const falta = AUSENTE.has(j.status[ind.id]);
    s.append(svg("line", { x1: c, y1: c, x2: pt(i, 100)[0], y2: pt(i, 100)[1], stroke: falta ? "var(--ausente)" : "var(--axis)", "stroke-dasharray": falta ? "2 3" : null }));
    const [lx, ly] = pt(i, 124);
    const anchor = Math.abs(lx - c) < 8 ? "middle" : lx > c ? "start" : "end";
    const t = svg("text", { x: lx, y: ly, "text-anchor": anchor, "dominant-baseline": "middle" });
    t.append(svg("tspan", { x: lx, class: "rotulo-dado", style: "font-size:14px" }, ROTULO_CURTO[ind.id]));
    t.append(svg("tspan", { x: lx, dy: 16, style: `font-size:13px${falta ? ";font-style:italic" : ""}` }, falta ? "não testou" : `p${pctTxt(j.pct[ind.id])}`));
    s.append(t);
  });
  // Polígono só pelos eixos medidos: eixo sem teste não é puxado para o centro (não é valor mínimo)
  const medidos = IND.map((ind, i) => ({ ind, i })).filter(({ ind }) => j.pct[ind.id] != null);
  if (medidos.length === n) {
    s.append(svg("polygon", { points: medidos.map(({ ind, i }) => pt(i, j.pct[ind.id]).join(",")).join(" "),
      fill: "color-mix(in srgb, var(--series-1) 18%, transparent)", stroke: "var(--series-1)", "stroke-width": 2, "stroke-linejoin": "round" }));
  } else {
    // Com eixo faltante não há área: só liga eixos vizinhos medidos, para o vazio não parecer valor baixo
    IND.forEach((ind, i) => {
      const prox = IND[(i + 1) % n];
      if (j.pct[ind.id] == null || j.pct[prox.id] == null) return;
      const [x1, y1] = pt(i, j.pct[ind.id]), [x2, y2] = pt((i + 1) % n, j.pct[prox.id]);
      s.append(svg("line", { x1, y1, x2, y2, stroke: "var(--series-1)", "stroke-width": 2, "stroke-linecap": "round" }));
    });
  }
  for (const { ind, i } of medidos) {
    const [x, y] = pt(i, j.pct[ind.id]);
    const ponto = svg("circle", { cx: x, cy: y, r: 4.5, fill: "var(--series-1)", stroke: "var(--surface-1)", "stroke-width": 2 });
    const alvo = svg("circle", { cx: x, cy: y, r: 12, fill: "transparent" });
    alvo.addEventListener("pointermove", (e) => mostrarDica(e, `<strong>${ind.nome}</strong><br>${fmtValor(ind, j.valores[ind.id], j)} · percentil ${pctTxt(j.pct[ind.id])}`));
    alvo.addEventListener("pointerleave", esconderDica);
    s.append(ponto, alvo);
  }
  return s;
}

// ---------- gráficos de dispersão ----------
function dispersao({ pontos, rotY, rotX, yLog = false, inverter = false, yMin, yMax, linhaZero = false, rotulos = [] }) {
  const W = 560, H = 340, m = { t: 12, r: 16, b: 40, l: 56 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const tY = yLog ? Math.log : (v) => v;
  const y0 = tY(yMin), y1 = tY(yMax);
  const sx = (v) => m.l + (v / 100) * iw;
  const fr = (v) => (tY(v) - y0) / (y1 - y0);
  const sy = (v) => (inverter ? m.t + fr(v) * ih : m.t + ih - fr(v) * ih);
  const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${rotY} por ${rotX}; ${pontos.length} jogadores` });
  const grade = svg("g", { class: "grade" }), eixo = svg("g", { class: "eixo" });
  for (const x of [0, 25, 50, 75, 100]) {
    grade.append(svg("line", { x1: sx(x), x2: sx(x), y1: m.t, y2: m.t + ih }));
    eixo.append(svg("text", { x: sx(x), y: H - m.b + 16, "text-anchor": "middle" }, String(x)));
  }
  const ticksY = yLog ? [1, 3, 10, 32, 100, 260].filter((v) => v >= yMin && v <= yMax) : ticksLineares(yMin, yMax);
  for (const v of ticksY) {
    grade.append(svg("line", { x1: m.l, x2: m.l + iw, y1: sy(v), y2: sy(v) }));
    eixo.append(svg("text", { x: m.l - 6, y: sy(v), "text-anchor": "end", "dominant-baseline": "middle" }, fmt(v)));
  }
  if (linhaZero) eixo.append(svg("line", { x1: m.l, x2: m.l + iw, y1: sy(0), y2: sy(0), stroke: "var(--text-muted)" }));
  eixo.append(svg("text", { x: m.l + iw / 2, y: H - 4, "text-anchor": "middle" }, rotX));
  eixo.append(svg("text", { x: 12, y: m.t + ih / 2, "text-anchor": "middle", transform: `rotate(-90 12 ${m.t + ih / 2})` }, rotY));
  s.append(grade, eixo);
  const camada = svg("g");
  for (const p of pontos) {
    const cx = sx(p.x), cy = sy(Math.min(Math.max(p.y, yMin), yMax));
    const ponto = svg("circle", { cx, cy, r: p.destaque ? 5 : 3.5, fill: p.cor, "fill-opacity": p.destaque ? 1 : 0.7,
      stroke: "var(--surface-1)", "stroke-width": p.destaque ? 2 : 1 });
    const alvo = svg("circle", { cx, cy, r: 9, fill: "transparent", style: "cursor:pointer" });
    alvo.addEventListener("pointermove", (e) => mostrarDica(e, p.dica));
    alvo.addEventListener("pointerleave", esconderDica);
    alvo.addEventListener("click", () => irPara("perfil", p.id));
    camada.append(ponto, alvo);
  }
  s.append(camada);
  // Rótulos seletivos, empurrados na vertical para não se sobreporem (mínimo 13 px entre linhas do mesmo lado)
  const posR = rotulos.map((p) => { const cx = sx(p.x), cy = sy(Math.min(Math.max(p.y, yMin), yMax)); return { p, cx, cy, dir: cx < m.l + iw * 0.6, ty: cy - 6 }; });
  for (const lado of [true, false]) {
    const g = posR.filter((r) => r.dir === lado).sort((a, b) => a.ty - b.ty);
    for (let i = 1; i < g.length; i++) if (g[i].ty - g[i - 1].ty < 13) g[i].ty = g[i - 1].ty + 13;
    const excesso = g.length ? g.at(-1).ty - (m.t + ih - 4) : 0;
    if (excesso > 0) g.forEach((r) => { r.ty -= excesso; });
  }
  for (const r of posR) {
    s.append(svg("line", { x1: r.cx, y1: r.cy, x2: r.cx + (r.dir ? 6 : -6), y2: r.ty + 3, stroke: "var(--text-muted)", "stroke-width": 1 }));
    s.append(svg("text", { x: r.cx + (r.dir ? 8 : -8), y: r.ty, "text-anchor": r.dir ? "start" : "end", class: "rotulo-dado" }, r.p.nome));
  }
  return s;
}
function ticksLineares(a, b) {
  const passo = [100, 250, 500, 1000, 2000, 2500, 5000].find((p) => (b - a) / p <= 6);
  const r = [];
  for (let v = Math.ceil(a / passo) * passo; v <= b; v += passo) r.push(v);
  return r;
}
function pontoDica(j, k, linhas) {
  return `<strong>${esc(j.nome)}</strong> (${j.ano}, pick ${j.pick})<br>percentil composto ${pctTxt(j.nota[k])}${linhas ? "<br>" + linhas : ""}`;
}

// ---------- tela: validação ----------
const fmtR = (m) => (m.valor >= 0 ? "+" : "−") + Math.abs(m.valor).toFixed(2).replace(".", ",");
const fmtIC = (m) => `IC 95%: ${m.ic95.map((v) => v.toFixed(2).replace(".", ",")).join(" a ")} · n = ${m.n}`;
function renderValidacao() {
  const el = $("#validacao");
  const k = estado.peso;
  const V = D.validacao[k];
  const P = V.passados;
  const idx = new Map(D.jogadores.map((j, i) => [j.id, i]));
  const disc = new Set([...V.discrepancias.nota_acima_da_producao.slice(0, 3), ...V.discrepancias.producao_acima_da_nota.slice(0, 3)]);
  const passados = D.jogadores.filter((j) => j.ano <= REF_FIM && j.desfecho && j.nota[k] != null);
  const todos = D.jogadores.filter((j) => j.nota[k] != null);

  // Calibração temporal: escolhe o peso pela 1ª metade e mede na 2ª (não usa a 2ª para escolher)
  const melhor = D.validacao.reduce((a, v, i) => (v.passados_primeira_metade.parcial_nota_desfecho_dado_pick.valor >
    D.validacao[a].passados_primeira_metade.parcial_nota_desfecho_dado_pick.valor ? i : a), 0);

  el.innerHTML = `
    <h2>A nota acerta? Validação com Drafts passados</h2>
    <p class="lead">Coorte de validação: ${GRUPO} com 3 temporadas completas na NFL (até ${M.ultima_temporada_completa}).
      Desfecho: jardas recebidas na temporada regular nas 3 primeiras temporadas; quem nunca jogou conta como 0.
      ${M.n_sem_gsis} jogadores sem ID na base da NFL ficaram de fora. Correlação de Spearman: de −1 a +1, compara ordens, não valores.
      Mostrando o cenário com ${pesoTxt(k)} de peso atlético.</p>
    <div class="metricas">
      ${cartaoMetrica("Nota × produção na NFL", P.nota_x_desfecho, "Quanto a ordem da nota acompanha a ordem de jardas.")}
      ${cartaoMetrica("Pick real × produção (referência)", P.pick_x_desfecho, "O mercado é a base a bater: pick alto também recebe mais alvos.")}
      ${cartaoMetrica("Nota × produção, descontado o pick", P.parcial_nota_desfecho_dado_pick,
        "Spearman parcial: o que a nota acrescenta à informação do pick. É a pergunta central.")}
      ${cartaoMetrica("Nota × pick real", P.nota_x_pick, "Quanto a nota pensa parecido com o mercado.")}
    </div>
    <div class="cartao">
      <strong>Leitura:</strong> o pick real ordena a produção bem melhor que a nota (${fmtR(P.pick_x_desfecho)} contra ${fmtR(P.nota_x_desfecho)}).
      Descontado o pick, a nota ainda carrega um sinal ${P.parcial_nota_desfecho_dado_pick.ic95[0] > 0 ? "pequeno e positivo" : "que não se distingue de zero"}
      (${fmtR(P.parcial_nota_desfecho_dado_pick)}). Ela serve como segunda opinião ao lado do Draft, não como substituta.
      <br><br><strong>Estabilidade no tempo:</strong> Drafts ${REF_INI}–${M.metade}: ${fmtR(V.passados_primeira_metade.parcial_nota_desfecho_dado_pick)};
      Drafts ${M.metade + 1}–${REF_FIM}: ${fmtR(V.passados_segunda_metade.parcial_nota_desfecho_dado_pick)} (Spearman parcial).
      <br><strong>Peso escolhido só com os Drafts antigos:</strong> ${pesoTxt(melhor)} de peso atlético maximiza o parcial em ${REF_INI}–${M.metade};
      aplicado a ${M.metade + 1}–${REF_FIM}, dá ${fmtR(D.validacao[melhor].passados_segunda_metade.parcial_nota_desfecho_dado_pick)},
      contra ${fmtR(D.validacao[BASE].passados_segunda_metade.parcial_nota_desfecho_dado_pick)} no peso base de ${pesoTxt(BASE)}.
      <br><strong>Desfecho secundário (eficiência):</strong> nota × jardas por alvo = ${fmtR(V.eficiencia_nota_x_jardas_por_alvo)}
      (${fmtIC(V.eficiencia_nota_x_jardas_por_alvo)}; só WRs com ${M.min_alvos_eficiencia}+ alvos nas 3 temporadas).
      <br><strong>Benchmark:</strong> o ranking pré-Draft da CFBD tem ${fmtR(D.benchmark_ranking_pre_draft)} com a produção
      (n = ${D.benchmark_ranking_pre_draft.n}, só quem tinha ranking).
      <br><strong>Classes recentes (${REF_FIM + 1}–${anos[0]}):</strong> nota × pick real = ${fmtR(V.recentes_nota_x_pick)} (${fmtIC(V.recentes_nota_x_pick)}); ainda sem carreira para comparar.
    </div>

    <div class="graficos">
      <div class="cartao grafico">
        <p class="titulo">Nota × pick real</p>
        <p class="subtitulo">Cada ponto é um WR. Pick em escala log (1 no topo).
          <span style="color:var(--series-1)">●</span> ${REF_INI}–${REF_FIM} &nbsp; <span style="color:var(--series-2)">●</span> ${REF_FIM + 1}–${anos[0]}</p>
        <div id="g-pick"></div>
      </div>
      <div class="cartao grafico">
        <p class="titulo">Nota × produção nas 3 primeiras temporadas</p>
        <p class="subtitulo">
          <label><input type="radio" name="eixoY" value="jardas" ${estado.eixoY === "jardas" ? "checked" : ""}> jardas</label>
          <label><input type="radio" name="eixoY" value="residuo" ${estado.eixoY === "residuo" ? "checked" : ""}> jardas acima do esperado pelo pick</label>
          · <span style="color:var(--series-2)">●</span> maiores discrepâncias</p>
        <div id="g-desfecho"></div>
      </div>
    </div>

    <h3>Maiores discrepâncias entre a nota e a produção</h3>
    <p class="lead">Diferença entre o percentil da nota e o percentil de jardas <em>acima do esperado pelo pick</em>. Comparar com jardas brutas
      só listaria picks tardios que nunca tiveram chance; descontar o pick isola o que a nota errou. São casos a investigar: o que a nota não vê
      (lesão, esquema, quarterback, nível da conferência) costuma explicar boa parte.</p>
    <div class="graficos">
      ${tabelaDisc("Nota acima da produção", V.discrepancias.nota_acima_da_producao, V, idx, k)}
      ${tabelaDisc("Produção acima da nota", V.discrepancias.producao_acima_da_nota, V, idx, k)}
    </div>

    <h3>Quem não fez os testes do Combine (${REF_INI}–${REF_FIM})</h3>
    <p class="lead">Se faltar teste fosse aleatório, os dois grupos seriam parecidos. Não são: quem não testou foi draftado mais tarde e produziu menos.
      Por isso o teste ausente aparece como "não testou" e nunca recebe um valor inventado.</p>
    <div class="cartao tabela-rolagem"><table>
      <thead><tr><th>Teste</th><th>Grupo</th><th class="num">WRs</th><th class="num">Pick mediano</th><th class="num">% 1ª rodada</th><th class="num">Jardas medianas (3 temp.)</th></tr></thead>
      <tbody>${D.nao_testou.map((r) => `<tr><td>${r.teste}</td><td>${r.grupo}</td><td class="num">${r.n}</td><td class="num">${fmt(r.pick_mediano)}</td>
        <td class="num">${fmt(r.primeira_rodada_pct, 1)}</td><td class="num">${fmt(r.jardas_medianas)}</td></tr>`).join("")}</tbody></table></div>

    <h3>Cobertura dos dados por classe (% dos WRs draftados)</h3>
    <div class="cartao tabela-rolagem"><table class="cob larga">
      <thead><tr><th>Classe</th><th>WRs</th><th>Foi ao Combine</th><th>40 jardas</th><th>Vertical</th><th>3-cone</th><th>Altura medida</th><th>Produção (CFBD)</th><th>ID NFL</th></tr></thead>
      <tbody>${D.cobertura.map((c) => `<tr><td>${c.ano}${c.ano === 2021 ? "*" : ""}</td><td>${c.n}</td>${["foi_ao_combine", "forty", "vertical", "cone", "altura_medida", "producao_cfbd", "gsis_id"]
        .map((k2) => `<td style="background:${corCobertura(c[k2])}">${fmt(c[k2])}</td>`).join("")}</tr>`).join("")}</tbody></table>
      <p class="nota-rodape">* 2021 sem Combine presencial: os números são, provavelmente, de Pro Day. O 3-cone fica fora da nota pela cobertura baixa.
        Em ${anos[0]} a base do Combine pode estar incompleta.</p></div>`;

  $("#g-pick").append(dispersao({
    pontos: todos.map((j) => ({ id: j.id, x: j.nota[k], y: j.pick, cor: j.ano > REF_FIM ? "var(--series-2)" : "var(--series-1)",
      dica: pontoDica(j, k) })),
    rotX: "percentil composto", rotY: "pick (log)", yLog: true, inverter: true, yMin: 1, yMax: 260,
  }));
  const ehRes = estado.eixoY === "residuo";
  const valY = (j) => (ehRes ? V.residuo[idx.get(j.id)] : j.desfecho.jardas);
  const ys = passados.map(valY);
  const pts = passados.map((j) => ({ id: j.id, x: j.nota[k], y: valY(j), destaque: disc.has(j.id),
    cor: disc.has(j.id) ? "var(--series-2)" : "var(--series-1)",
    dica: pontoDica(j, k, `${fmt(j.desfecho.jardas)} jardas nas 3 primeiras temporadas<br>${fmt(V.residuo[idx.get(j.id)])} em relação ao esperado pelo pick`) }));
  $("#g-desfecho").append(dispersao({
    pontos: pts.sort((a, b) => a.destaque - b.destaque), rotX: "percentil composto",
    rotY: ehRes ? "jardas acima do esperado" : "jardas (3 temporadas)",
    yMin: ehRes ? Math.floor(Math.min(...ys) / 500) * 500 : 0, yMax: Math.ceil(Math.max(...ys) / 500) * 500, linhaZero: ehRes,
    rotulos: pts.filter((p) => p.destaque).map((p) => ({ ...p, nome: porId.get(p.id).nome })),
  }));
  el.querySelectorAll('input[name="eixoY"]').forEach((r) => r.addEventListener("change", (e) => { estado.eixoY = e.target.value; render(); }));
  el.querySelectorAll("tr[data-id]").forEach((tr) => tr.addEventListener("click", () => irPara("perfil", tr.dataset.id)));
}
function cartaoMetrica(rot, m, texto) {
  return `<div class="metrica"><div class="rot">${rot}</div><div class="val tnum">${fmtR(m)}</div><div class="ic">${fmtIC(m)}</div><p>${texto}</p></div>`;
}
function tabelaDisc(titulo, ids, V, idx, k) {
  return `<div class="cartao tabela-rolagem"><p class="grafico titulo">${titulo}</p><table>
    <thead><tr><th>Jogador</th><th class="num">Pick</th><th class="num">Nota</th><th class="num">Pct. vs. pick</th><th class="num">Jardas</th></tr></thead>
    <tbody>${ids.map((id) => { const j = porId.get(id); return `<tr data-id="${id}" style="cursor:pointer"><td>${esc(j.nome)} <span class="nota-rodape">${j.ano}</span></td>
      <td class="num">${j.pick}</td><td class="num">${pctTxt(j.nota[k])}</td><td class="num">${pctTxt(V.desfecho_pct[idx.get(id)])}</td>
      <td class="num">${fmt(j.desfecho.jardas)}</td></tr>`; }).join("")}</tbody></table></div>`;
}
function corCobertura(v) {
  if (v == null) return "transparent";
  // rampa sequencial de uma cor só: mais cobertura = mais azul
  return `color-mix(in srgb, var(--series-1) ${Math.round((v / 100) * 32)}%, transparent)`;
}

// ---------- tela: metodologia ----------
function renderMetodologia() {
  const el = $("#metodologia");
  el.innerHTML = `
    <h2>Metodologia</h2>
    <p class="lead"><strong>Pergunta de decisão:</strong> como este WR se compara a WRs draftados antes, em perfil atlético e em produção
      universitária ajustada à oportunidade? E o quanto esse tipo de perfil se traduziu em produção nas 3 primeiras temporadas na NFL?</p>
    <div class="cartao">
      <strong>Como a nota é feita.</strong> Cada indicador vira percentil entre ${GRUPO}. Os percentis são combinados em dois blocos,
      atlético e produção, e os blocos são misturados pelo peso escolhido no controle (base: ${pesoTxt(BASE)} atlético). A mistura vira de novo
      percentil no mesmo grupo. Indicador sem dado sai da média do bloco (os pesos dos outros são reescalados), e a tela mostra a faixa do que
      a nota seria se ele existisse. Os pesos são <em>declarados pela equipe</em>, não estimados nos dados; a aba Validação mostra o que acontece
      com cada peso e uma escolha feita só com os Drafts antigos.
    </div>
    <h3>Fundamentação dos indicadores</h3>
    <div class="cartao tabela-rolagem"><table class="larga">
      <thead><tr><th>Indicador</th><th>Bloco</th><th>Origem</th><th>Fonte</th><th>Dado</th><th class="num">Peso no bloco</th><th>Justificativa do peso</th></tr></thead>
      <tbody>${IND.map((i) => `<tr><td>${i.nome}</td><td>${i.grupo === "atletico" ? "atlético" : "produção"}</td><td>${i.origem}</td>
        <td>${esc(i.fonte)}</td><td>${esc(i.dado).replace(/`([^`]+)`/g, "<code>$1</code>")}</td>
        <td class="num">${Math.round(i.peso_no_grupo * 100)}%</td><td>${esc(i.justificativa_peso)}</td></tr>`).join("")}
        <tr><td>Nota composta</td><td>—</td><td>Proposta da equipe</td><td>este projeto</td><td>percentis acima</td><td class="num">—</td>
          <td>Peso atlético ajustável de 0 a 50%; a validação mostra a sensibilidade.</td></tr></tbody></table>
      <p class="nota-rodape">Origem: <em>literatura</em> = artigo revisado por pares; <em>prática de mercado</em> = métrica da mídia ou da comunidade
        de analytics, sem revisão por pares; <em>proposta da equipe</em> = escolha nossa, sustentada pela validação.</p></div>
    <h3>Ficaram de fora</h3>
    <div class="cartao"><ul>${D.descartados.map((d) => `<li><strong>${d.nome}:</strong> ${esc(d.motivo)}</li>`).join("")}</ul></div>
    <h3>Regras de dados</h3>
    <div class="cartao"><ul>
      <li>Jogadores ligados entre bases por ID (pfr_id; ano + pick na CFBD), nunca por nome.</li>
      <li>Teste não realizado aparece como "não testou". Nunca recebe o valor mínimo nem a média.</li>
      <li>2021 não teve Combine presencial; os testes dessa classe são marcados como provável Pro Day.</li>
      <li>Sem altura medida no Combine, usamos a altura listada pela CFBD, marcada como tal.</li>
      <li>Fatia das jardas: jardas do jogador ÷ jardas de todos os recebedores do time, no último ano universitário com estatística.
        Quem não jogou o último ano (ex.: opt-out em 2020) usa a temporada anterior, com aviso.</li>
      <li>Idade de breakout: idade aproximada na primeira temporada com ${Math.round(M.limiar_breakout * 100)}% ou mais das jardas do time.
        Quem nunca chegou lá recebe a pior posição (é um resultado, não dado faltante).</li>
      <li>Desfecho na NFL: jardas na temporada regular nas 3 primeiras temporadas. Quem tem ID e não aparece nas estatísticas conta como 0.
        Jardas por alvo é desfecho secundário, só com ${M.min_alvos_eficiencia}+ alvos (${M.n_eficiencia} WRs).</li>
    </ul></div>
    <h3>O que a nota não vê</h3>
    <div class="cartao"><p style="margin:0">Lesões e exames médicos, entrevistas, rotas e técnica no vídeo, esquema tático, qualidade do quarterback
      universitário, força das defesas enfrentadas, contexto do time que draftou. WRs vindos de escolas fora da CFBD ou com anos em junior college
      têm produção incompleta. A comparação é sempre com WRs <em>draftados</em>: a ferramenta não avalia quem não foi draftado.</p></div>
    <h3>Persona: Diretor de Scouting</h3>
    <div class="cartao aviso" style="margin:0">Pendente: a equipe precisa listar aqui as fontes que sustentam as atribuições da persona
      (pedido do professor). Elas estavam na Memória da Etapa II em Power BI, que não estava na pasta do projeto.</div>
    <h3>Fontes de dados</h3>
    <div class="cartao"><ul>${M.fontes.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
      <p class="nota-rodape">Dados gerados em ${M.gerado_em}. Grupo de comparação: ${GRUPO}. Última temporada completa da NFL: ${M.ultima_temporada_completa}.</p></div>`;
}

// ---------- render ----------
function render() {
  document.querySelectorAll("nav.abas button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tela === estado.tela)));
  document.querySelectorAll("section.tela").forEach((s) => { s.hidden = s.id !== estado.tela; });
  $("#controles-globais").hidden = estado.tela === "metodologia";
  esconderDica();
  desenharControles();
  ({ ranking: renderRanking, perfil: renderPerfil, validacao: renderValidacao, metodologia: renderMetodologia })[estado.tela]();
}
lerEndereco();
render();
