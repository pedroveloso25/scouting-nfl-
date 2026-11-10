"""Indicadores do ranking de WR: fundamentação, cálculo dos valores brutos e percentis.

A tabela INDICADORES é a fonte única da fundamentação: o pipeline a exporta para o wr.json e a tela
de Metodologia a lê de lá. Mudou um peso ou uma fonte? Mude aqui.

Regras de negócio:
- Percentil sempre contra o mesmo grupo de comparação (WRs draftados em JANELA_REFERENCIA).
- Para fora = melhor: indicadores em que menor é melhor (idades) são invertidos antes do percentil.
- Teste não realizado fica nulo e entra no wr.json com o status "não testou". A nota composta usa só
  os indicadores disponíveis e mostra a faixa do que ela seria se o teste tivesse qualquer resultado.
"""

import math

import numpy as np
import polars as pl

# Drafts com produção universitária ligável por ID na CFBD (antes de 2010 os IDs não casam)
PRIMEIRO_DRAFT = 2010
# Grupo de comparação: WRs draftados com 3 temporadas completas na NFL até 2025
JANELA_REFERENCIA = (2010, 2023)
LIMIAR_BREAKOUT = 0.20
PESOS_ATLETICOS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]  # valores do controle "peso do perfil atlético"
PESO_BASE = 0.2

INDICADORES = [
    {
        "id": "altura", "nome": "Altura", "grupo": "atletico", "unidade": "pol", "maior_melhor": True,
        "peso_no_grupo": 1 / 3,
        "origem": "Literatura",
        "fonte": "Teramoto, Cross & Willick (2016), JSCR 30(5) — verificação secundária",
        "dado": "nflverse combine `ht`; sem medição, altura listada na CFBD /draft/picks (marcada)",
        "justificativa_peso": "Um terço do bloco atlético. A literatura aponta altura e salto vertical como os "
        "testes que mais se associam à produção de WR, mas não dá pesos relativos; dividimos igualmente.",
    },
    {
        "id": "vertical", "nome": "Salto vertical", "grupo": "atletico", "unidade": "pol", "maior_melhor": True,
        "peso_no_grupo": 1 / 3,
        "origem": "Literatura",
        "fonte": "Teramoto et al. (2016); Jensen & Mulholland, CHANCE (ano/volume a confirmar)",
        "dado": "nflverse combine `vertical`",
        "justificativa_peso": "Um terço do bloco atlético, pelo mesmo motivo da altura.",
    },
    {
        "id": "speed_score", "nome": "Speed Score", "grupo": "atletico", "unidade": "", "maior_melhor": True,
        "peso_no_grupo": 1 / 3,
        "origem": "Prática de mercado",
        "fonte": "Bill Barnwell (autoria a confirmar): peso × 200 / (40 jardas)⁴",
        "dado": "nflverse combine `wt` e `forty`",
        "justificativa_peso": "Um terço do bloco atlético. Ajusta a velocidade pelo peso; Kuzmits & Adams (2008) "
        "não acharam associação do sprint com sucesso de WR, por isso o bloco atlético inteiro pesa pouco (20% na base).",
    },
    {
        "id": "fatia_jardas", "nome": "Fatia das jardas do time", "grupo": "producao", "unidade": "%",
        "maior_melhor": True, "peso_no_grupo": 0.5,
        "origem": "Literatura + prática",
        "fonte": "Jensen & Mulholland, CHANCE (fatia das jardas no último ano); dominator rating (RotoViz, PlayerProfiler)",
        "dado": "CFBD /stats/player/season (receiving): jardas do jogador ÷ jardas de todos os recebedores do time, "
        "no último ano universitário com estatística",
        "justificativa_peso": "Metade do bloco de produção: é a única métrica de produção com apoio acadêmico, e "
        "mede produção por oportunidade (fatia do time), não volume bruto.",
    },
    {
        "id": "breakout_idade", "nome": "Idade de breakout", "grupo": "producao", "unidade": "anos",
        "maior_melhor": False, "peso_no_grupo": 0.25,
        "origem": "Prática de mercado",
        "fonte": "RotoViz (breakout age); limiar de 20% da PlayerProfiler (a RotoViz usa 30%)",
        "dado": f"CFBD: primeira temporada com fatia ≥ {LIMIAR_BREAKOUT:.0%} das jardas; idade aproximada pela "
        "idade no Draft (nflverse `age`) menos os anos até o Draft",
        "justificativa_peso": "Um quarto do bloco de produção. Divide o peso restante com a idade no Draft porque "
        "as duas medem precocidade; dar meio bloco a cada uma contaria idade duas vezes.",
    },
    {
        "id": "idade_draft", "nome": "Idade no Draft", "grupo": "producao", "unidade": "anos",
        "maior_melhor": False, "peso_no_grupo": 0.25,
        "origem": "Prática de mercado",
        "fonte": "Sharp Football (2020), early declare",
        "dado": "nflverse draft picks `age`",
        "justificativa_peso": "Um quarto do bloco de produção (ver idade de breakout).",
    },
]
IDS = [i["id"] for i in INDICADORES]
DESCARTADOS = [
    {"nome": "3-cone", "motivo": "Cobertura de ~20% entre os WRs draftados de 2023 a 2025; viraria eixo quase vazio."},
    {"nome": "40 jardas isolada", "motivo": "Entra via Speed Score, que já usa o tempo ajustado pelo peso."},
    {"nome": "Jardas, TDs e recepções totais", "motivo": "Medem volume, não oportunidade: favorecem quem jogou mais "
     "anos ou em ataques que passam mais."},
    {"nome": "Yards per route run", "motivo": "Sem dado gratuito (PFF) e com transferência fraca para a NFL (PFF 2018)."},
]


def _altura_pol(ht: pl.Expr) -> pl.Expr:
    """'6-1' (pés-polegadas) -> 73 polegadas."""
    partes = ht.str.split("-")
    return partes.list.get(0, null_on_oob=True).cast(pl.Float64, strict=False) * 12 + partes.list.get(
        1, null_on_oob=True).cast(pl.Float64, strict=False)


def combine_wr(draft: pl.DataFrame, combine: pl.DataFrame) -> pl.DataFrame:
    """Testes do Combine por jogador draftado. Join por pfr_id; ano + pick só quando o pfr_id falta.

    O fallback por ano + pick confere a posição: casar por pick puro trazia TE, FB e P em 6 casos.
    """
    testes = combine.select(
        "pfr_id", pl.col("draft_year").cast(pl.Int32), pl.col("draft_ovr").cast(pl.Int32), "pos",
        "ht", "wt", "forty", "vertical", "cone",
    ).with_columns(_altura_pol(pl.col("ht")).alias("altura_combine"))
    por_id = draft.join(testes.filter(pl.col("pfr_id").is_not_null()).unique("pfr_id"),
                        left_on="pfr_player_id", right_on="pfr_id", how="left")
    sem_id = por_id.filter(pl.col("pfr_player_id").is_null()).select(draft.columns)
    por_pick = sem_id.join(
        testes.filter(pl.col("pos").str.contains("WR")).drop("pfr_id"),
        left_on=["season", "pick"], right_on=["draft_year", "draft_ovr"], how="left",
    )
    com_id = por_id.filter(pl.col("pfr_player_id").is_not_null()).drop("draft_year", "draft_ovr", strict=False)
    return pl.concat([com_id, por_pick], how="diagonal_relaxed").with_columns(
        pl.col("pos").is_not_null().alias("tem_combine")
    )


def producao_universitaria(rec_longo: pl.DataFrame) -> pl.DataFrame:
    """Uma linha por jogador × temporada com a fatia das jardas do time.

    O total do time é a soma das jardas de todos os recebedores na mesma base; em 2023 essa soma bate
    com o netPassingYards da CFBD (razão média 1,000), então dispensa um endpoint a mais.
    """
    largo = (
        rec_longo.filter(pl.col("statType").is_in(["REC", "YDS", "TD"]))
        .with_columns(pl.col("stat").cast(pl.Float64, strict=False))
        .pivot(on="statType", index=["season", "playerId", "team"], values="stat", aggregate_function="sum")
    )
    times = largo.group_by("season", "team").agg(pl.col("YDS").sum().alias("jardas_time"))
    return (
        largo.join(times, on=["season", "team"])
        .group_by("playerId", "season")  # quem trocou de time na temporada soma as duas passagens
        .agg(pl.col("YDS").sum().alias("jardas"), pl.col("REC").sum().alias("recepcoes"),
             pl.col("TD").sum().alias("tds"), pl.col("jardas_time").sum(), pl.col("team").last().alias("time"))
        .with_columns(
            pl.when(pl.col("jardas_time") > 0).then(pl.col("jardas") / pl.col("jardas_time")).alias("fatia")
        )
    )


def indicadores_producao(wr: pl.DataFrame, temporadas: pl.DataFrame) -> pl.DataFrame:
    """Fatia no último ano universitário e idade de breakout, por jogador draftado."""
    t = (
        wr.select("id", "season", "age", "college_id")
        .join(temporadas, left_on="college_id", right_on="playerId", how="inner")
        .filter(pl.col("season_right") <= pl.col("season") - 1)
        .rename({"season_right": "temporada"})
    )
    ultimo = (
        t.sort("temporada").group_by("id").agg(
            pl.col("fatia").last().alias("fatia_jardas"),
            pl.col("temporada").last().alias("fatia_temporada"),
            pl.col("jardas").last().alias("jardas_ultimo_ano"),
            pl.col("time").last().alias("time_ultimo_ano"),
            pl.len().alias("temporadas_cfbd"),
        )
    )
    breakout = (
        t.filter(pl.col("fatia") >= LIMIAR_BREAKOUT)
        .group_by("id")
        .agg(pl.col("temporada").min().alias("breakout_temporada"), pl.col("season").first(), pl.col("age").first())
        .with_columns((pl.col("age") - (pl.col("season") - pl.col("breakout_temporada"))).cast(pl.Float64)
                      .alias("breakout_idade"))
        .select("id", "breakout_temporada", "breakout_idade")
    )
    return ultimo.join(breakout, on="id", how="left").with_columns(
        # Tem temporadas na CFBD e nunca chegou a 20%: resultado real (pior posição), não dado faltante
        pl.when(pl.col("breakout_idade").is_null()).then(pl.lit(math.inf)).otherwise(pl.col("breakout_idade"))
        .alias("breakout_idade"),
        pl.col("breakout_idade").is_null().alias("breakout_nao_atingiu"),
    )


def percentil(valores: np.ndarray, referencia: np.ndarray, maior_melhor: bool) -> np.ndarray:
    """Percentil de cada valor contra a referência (empates contam meio). Nulo continua nulo."""
    ref = referencia[~np.isnan(referencia)]
    if not maior_melhor:
        valores, ref = -valores, -ref
    ref = np.sort(ref)
    abaixo = np.searchsorted(ref, valores, side="left")
    iguais = np.searchsorted(ref, valores, side="right") - abaixo
    pct = 100 * (abaixo + 0.5 * iguais) / len(ref)
    return np.where(np.isnan(valores), np.nan, pct)


def notas(pcts: dict[str, np.ndarray], peso_atletico: float, preencher: float | None = None) -> np.ndarray:
    """Nota bruta 0–100: média ponderada dos percentis disponíveis em cada bloco, depois dos blocos.

    Com `preencher`, os percentis faltantes viram esse valor (0 ou 100) para calcular a faixa do que a nota
    seria se o teste não realizado tivesse qualquer resultado. Sem ele, faltante sai da média do bloco.
    Bloco inteiro faltante: a nota usa só o outro bloco (e o wr.json avisa).
    """
    blocos = {}
    for grupo in ("atletico", "producao"):
        soma = peso = 0
        for ind in (i for i in INDICADORES if i["grupo"] == grupo):
            p = pcts[ind["id"]]
            if preencher is not None:
                p = np.where(np.isnan(p), preencher, p)
            ok = ~np.isnan(p)
            soma = soma + np.where(ok, p, 0) * ind["peso_no_grupo"]
            peso = peso + ok * ind["peso_no_grupo"]
        blocos[grupo] = np.where(peso > 0, soma / np.where(peso > 0, peso, 1), np.nan)
    a, p = blocos["atletico"], blocos["producao"]
    if peso_atletico == 0:
        return p
    mistura = peso_atletico * a + (1 - peso_atletico) * p
    return np.where(np.isnan(a), p, np.where(np.isnan(p), a, mistura))
