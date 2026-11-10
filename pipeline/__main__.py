"""Pipeline completo: dados brutos -> indicadores -> validação -> web/data/wr.json (+ wr.js).

Uso: uv run python -m pipeline [--atualizar]

--atualizar baixa tudo de novo (nflverse e CFBD); sem ele, reaproveita data/raw/.
O wr.js tem o mesmo conteúdo do wr.json, embrulhado numa variável global, para o HTML abrir com
duplo clique (file://), onde o navegador bloqueia fetch() de arquivos locais.
"""

import argparse
import json
import sys
import math
from datetime import date

import numpy as np
import polars as pl

from . import fontes
from .indicadores import (
    DESCARTADOS, IDS, INDICADORES, JANELA_REFERENCIA, LIMIAR_BREAKOUT, PESO_BASE, PESOS_ATLETICOS,
    PRIMEIRO_DRAFT, combine_wr, indicadores_producao, notas, percentil, producao_universitaria,
)
from .validacao import com_intervalo, metricas, residuo_log_pick, spearman

ULTIMA_TEMPORADA_COMPLETA = 2025
JANELA_NFL = 3  # temporadas
MIN_ALVOS_EFICIENCIA = 50
SAIDA = fontes.RAIZ / "web" / "data"


def montar_base(atualizar: bool) -> pl.DataFrame:
    draft = (
        fontes.draft_picks(atualizar)
        .filter((pl.col("position") == "WR") & (pl.col("season") >= PRIMEIRO_DRAFT))
        .select("season", "round", "pick", "team", "gsis_id", "pfr_player_id", "pfr_player_name", "college", "age")
    )
    anos = range(PRIMEIRO_DRAFT, int(draft["season"].max()) + 1)
    wr = combine_wr(draft, fontes.combine(atualizar))

    # CFBD /draft/picks de TODAS as posições: a CFBD às vezes lista como CB/RB quem o PFR chama de WR
    cfbd_picks = pl.DataFrame(
        [p for a in anos for p in fontes.cfbd("/draft/picks", atualizar, year=a)], infer_schema_length=None
    ).select(
        pl.col("year").cast(pl.Int32).alias("season"), pl.col("overall").cast(pl.Int32).alias("pick"),
        pl.col("collegeAthleteId").cast(pl.Utf8).alias("college_id"), pl.col("collegeConference").alias("conferencia"),
        pl.col("height").cast(pl.Float64).alias("altura_cfbd"), pl.col("preDraftRanking").alias("ranking_pre_draft"),
        pl.col("preDraftPositionRanking").alias("ranking_pre_draft_posicao"),
    )
    wr = wr.join(cfbd_picks, on=["season", "pick"], how="left").with_columns(
        pl.format("{}-{}", "season", "pick").alias("id")
    )

    temporadas_cfbd = range(PRIMEIRO_DRAFT - 6, int(draft["season"].max()))
    rec = pl.concat(
        [pl.DataFrame(fontes.cfbd("/stats/player/season", atualizar, year=a, category="receiving"),
                      infer_schema_length=None) for a in temporadas_cfbd],
        how="diagonal_relaxed",
    )
    wr = wr.join(indicadores_producao(wr, producao_universitaria(rec)), on="id", how="left")
    return wr


def desfecho_nfl(wr: pl.DataFrame, atualizar: bool) -> pl.DataFrame:
    """Jardas, alvos e jogos nas 3 primeiras temporadas regulares. Com gsis_id e sem linha = 0."""
    stats = fontes.player_stats(list(range(PRIMEIRO_DRAFT, ULTIMA_TEMPORADA_COMPLETA + 1)), atualizar)
    return janela_nfl(wr, stats)


def janela_nfl(wr: pl.DataFrame, stats: pl.DataFrame) -> pl.DataFrame:
    elegiveis = wr.filter(pl.col("season") + JANELA_NFL - 1 <= ULTIMA_TEMPORADA_COMPLETA).select("id", "season", "gsis_id")
    janela = (
        elegiveis.filter(pl.col("gsis_id").is_not_null())
        .join(stats, left_on="gsis_id", right_on="player_id", how="left")
        .filter(pl.col("season_right").is_null()
                | pl.col("season_right").is_between(pl.col("season"), pl.col("season") + JANELA_NFL - 1))
        .group_by("id")
        .agg(
            pl.col("receiving_yards").sum().alias("jardas"), pl.col("targets").sum().alias("alvos"),
            pl.col("receptions").sum().alias("recepcoes"), pl.col("receiving_tds").sum().alias("tds"),
            pl.col("week").is_not_null().sum().alias("jogos"),
        )
    )
    return elegiveis.join(janela, on="id", how="left").with_columns(
        pl.col("gsis_id").is_null().alias("sem_gsis"),
        # Tem ID e nenhuma linha na janela: nunca jogou -> desfecho 0, não nulo
        *[pl.when(pl.col("gsis_id").is_not_null()).then(pl.col(c).fill_null(0)).alias(c)
          for c in ("jardas", "alvos", "recepcoes", "tds", "jogos")],
    ).drop("season", "gsis_id")


def valores_e_status(wr: pl.DataFrame) -> pl.DataFrame:
    pro_day = pl.col("season") == 2021
    def teste(col: str) -> pl.Expr:
        return (pl.when(pl.col(col).is_not_null()).then(pl.when(pro_day).then(pl.lit("pro_day_2021"))
                                                       .otherwise(pl.lit("medido")))
                .when(pl.col("tem_combine")).then(pl.lit("nao_testou")).otherwise(pl.lit("sem_combine")))
    return wr.with_columns(
        pl.coalesce("altura_combine", "altura_cfbd").alias("v_altura"),
        pl.col("vertical").alias("v_vertical"),
        (pl.col("wt") * 200 / pl.col("forty") ** 4).alias("v_speed_score"),
        pl.col("fatia_jardas").alias("v_fatia_jardas"),
        pl.col("breakout_idade").alias("v_breakout_idade"),
        pl.col("age").cast(pl.Float64).alias("v_idade_draft"),
        pl.when(pl.col("altura_combine").is_not_null()).then(teste("altura_combine"))
        .when(pl.col("altura_cfbd").is_not_null()).then(pl.lit("altura_listada"))
        .otherwise(teste("altura_combine")).alias("s_altura"),
        teste("vertical").alias("s_vertical"),
        pl.when(pl.col("wt").is_not_null() & pl.col("forty").is_not_null()).then(teste("forty"))
        .otherwise(pl.when(pl.col("tem_combine")).then(pl.lit("nao_testou")).otherwise(pl.lit("sem_combine")))
        .alias("s_speed_score"),
        pl.when(pl.col("fatia_jardas").is_null()).then(pl.lit("sem_dados_cfbd"))
        .when(pl.col("fatia_temporada") < pl.col("season") - 1).then(pl.lit("ultimo_ano_anterior"))
        .otherwise(pl.lit("medido")).alias("s_fatia_jardas"),
        pl.when(pl.col("fatia_jardas").is_null()).then(pl.lit("sem_dados_cfbd"))
        .when(pl.col("breakout_nao_atingiu")).then(pl.lit("nao_atingiu"))
        .otherwise(pl.lit("medido")).alias("s_breakout_idade"),
        pl.when(pl.col("age").is_null()).then(pl.lit("sem_dado")).otherwise(pl.lit("medido")).alias("s_idade_draft"),
    )


def _limpo(x):
    """NaN/inf -> None e floats arredondados, para JSON válido e enxuto."""
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    if isinstance(x, (float, np.floating)):
        return round(float(x), 3)
    if isinstance(x, np.integer):
        return int(x)
    return x


def cobertura_por_ano(df: pl.DataFrame) -> list[dict]:
    pct = lambda cond: (cond.mean() * 100).round(0)
    return df.group_by("season").agg(
        pl.len().alias("n"),
        pct(pl.col("tem_combine")).alias("foi_ao_combine"),
        pct(pl.col("forty").is_not_null()).alias("forty"),
        pct(pl.col("vertical").is_not_null()).alias("vertical"),
        pct(pl.col("cone").is_not_null()).alias("cone"),
        pct(pl.col("altura_combine").is_not_null()).alias("altura_medida"),
        pct(pl.col("v_fatia_jardas").is_not_null()).alias("producao_cfbd"),
        pct(pl.col("age").is_not_null()).alias("idade"),
        pct(pl.col("gsis_id").is_not_null()).alias("gsis_id"),
    ).sort("season").rename({"season": "ano"}).to_dicts()


def quem_nao_testou(df: pl.DataFrame) -> list[dict]:
    """Quem pula o teste não é aleatório (MNAR): compara pick e desfecho de quem testou e quem não."""
    linhas = []
    for teste, col in (("40 jardas", "forty"), ("Salto vertical", "vertical")):
        for testou in (True, False):
            g = df.filter(pl.col(col).is_not_null() == testou)
            linhas.append({
                "teste": teste, "grupo": "testou" if testou else "não testou", "n": g.height,
                "pick_mediano": _limpo(g["pick"].median()),
                "primeira_rodada_pct": _limpo(round(float((g["round"] == 1).mean() * 100), 1)),
                "jardas_medianas": _limpo(g["jardas"].median()),
            })
    return linhas


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # console do Windows (cp1252)
    parser = argparse.ArgumentParser(description="Gera web/data/wr.json")
    parser.add_argument("--atualizar", action="store_true", help="baixa os dados brutos de novo")
    args = parser.parse_args()

    wr = valores_e_status(montar_base(args.atualizar))
    wr = wr.join(desfecho_nfl(wr, args.atualizar), on="id", how="left").sort("season", "pick")
    ref = wr["season"].is_between(*JANELA_REFERENCIA).to_numpy()

    pcts = {}
    for ind in INDICADORES:
        v = wr[f"v_{ind['id']}"].cast(pl.Float64).fill_null(np.nan).to_numpy()
        pcts[ind["id"]] = percentil(v, v[ref], ind["maior_melhor"])

    nota_pct, faixas = [], []
    for w in PESOS_ATLETICOS:
        bruta = notas(pcts, w)
        nota_pct.append(percentil(bruta, bruta[ref], True))
        faixas.append((percentil(notas(pcts, w, 0), bruta[ref], True), percentil(notas(pcts, w, 100), bruta[ref], True)))

    # ---------- validação ----------
    jardas = wr["jardas"].cast(pl.Float64).fill_null(np.nan).to_numpy()
    pick = wr["pick"].cast(pl.Float64).to_numpy()
    validos = ref & ~np.isnan(jardas)
    alvos = wr["alvos"].cast(pl.Float64).fill_null(np.nan).to_numpy()
    com_alvos = validos & (alvos >= MIN_ALVOS_EFICIENCIA)
    por_alvo = np.where(com_alvos, jardas / np.where(alvos > 0, alvos, 1), np.nan)
    recentes = wr["season"].to_numpy() > JANELA_REFERENCIA[1]
    metade = (JANELA_REFERENCIA[0] + JANELA_REFERENCIA[1]) // 2
    validacao = []
    for k, w in enumerate(PESOS_ATLETICOS):
        n = nota_pct[k]
        ok = validos & ~np.isnan(n)
        res = np.full(len(wr), np.nan)
        res[ok] = residuo_log_pick(jardas[ok], pick[ok])
        # Discrepância contra o resíduo (jardas acima do esperado pelo pick), não contra jardas brutas:
        # pick tardio com 0 jardas é falta de oportunidade, não erro da nota
        pos_desfecho = np.full(len(wr), np.nan)
        pos_desfecho[ok] = percentil(res[ok], res[ok], True)
        dif = n - pos_desfecho
        idx = np.where(ok)[0]
        ordem = idx[np.argsort(dif[idx])]
        anos = wr["season"].to_numpy()
        ok_rec = recentes & ~np.isnan(n)
        validacao.append({
            "peso_atletico": w,
            "passados": metricas(n[ok], pick[ok], jardas[ok]),
            "passados_primeira_metade": metricas(*(a[ok & (anos <= metade)] for a in (n, pick, jardas))),
            "passados_segunda_metade": metricas(*(a[ok & (anos > metade)] for a in (n, pick, jardas))),
            # Desfecho secundário: só quem teve alvos suficientes, então mede eficiência entre quem jogou
            "eficiencia_nota_x_jardas_por_alvo": com_intervalo(spearman, n[com_alvos & ok], por_alvo[com_alvos & ok]),
            "recentes_nota_x_pick": com_intervalo(lambda a, b: spearman(a, -b), n[ok_rec], pick[ok_rec]),
            "residuo": [_limpo(r) for r in res],
            "desfecho_pct": [_limpo(p) for p in pos_desfecho],
            "discrepancias": {
                "nota_acima_da_producao": [wr["id"][int(i)] for i in ordem[::-1][:8]],
                "producao_acima_da_nota": [wr["id"][int(i)] for i in ordem[:8]],
            },
        })

    ranking_pre = wr["ranking_pre_draft"].cast(pl.Float64).fill_null(np.nan).to_numpy()
    ok_pre = validos & ~np.isnan(ranking_pre)
    benchmark = metricas(-ranking_pre[ok_pre], pick[ok_pre], jardas[ok_pre])["nota_x_desfecho"]


    # ---------- jogadores ----------
    jogadores = []
    for i, r in enumerate(wr.iter_rows(named=True)):
        avisos = []
        if r["season"] == 2021:
            avisos.append("2021 não teve Combine presencial: os testes deste ano são, provavelmente, de Pro Day.")
        if r["s_fatia_jardas"] == "ultimo_ano_anterior":
            avisos.append(f"Último ano universitário com estatística: {r['fatia_temporada']} (não jogou ou não há dado "
                          f"em {r['season'] - 1}).")
        if r["s_altura"] == "altura_listada":
            avisos.append("Altura listada pela CFBD, não medida no Combine.")
        jogadores.append({
            "id": r["id"], "nome": r["pfr_player_name"], "ano": r["season"], "rodada": r["round"], "pick": r["pick"],
            "time_nfl": r["team"], "universidade": r["college"], "conferencia": r["conferencia"],
            "ranking_pre_draft": r["ranking_pre_draft"],
            "valores": {k: _limpo(r[f"v_{k}"]) for k in IDS},
            "status": {k: r[f"s_{k}"] for k in IDS},
            "pct": {k: _limpo(pcts[k][i]) for k in IDS},
            "breakout_temporada": r["breakout_temporada"], "fatia_temporada": r["fatia_temporada"],
            "nota": [_limpo(n[i]) for n in nota_pct],
            "faixa": [[_limpo(lo[i]), _limpo(hi[i])] for lo, hi in faixas],
            "desfecho": None if r["jardas"] is None else {
                "jardas": r["jardas"], "alvos": r["alvos"], "recepcoes": r["recepcoes"], "tds": r["tds"],
                "jogos": r["jogos"],
                "jardas_por_alvo": _limpo(r["jardas"] / r["alvos"]) if r["alvos"] >= MIN_ALVOS_EFICIENCIA else None,
            },
            "sem_gsis": bool(r["sem_gsis"]) if r["sem_gsis"] is not None else None,
            "avisos": avisos,
        })

    passados = wr.filter(pl.col("season").is_between(*JANELA_REFERENCIA))
    dados = {
        "meta": {
            "gerado_em": date.today().isoformat(),
            "janela_referencia": list(JANELA_REFERENCIA),
            "janela_nfl_temporadas": JANELA_NFL,
            "ultima_temporada_completa": ULTIMA_TEMPORADA_COMPLETA,
            "pesos_atleticos": PESOS_ATLETICOS, "peso_base": PESO_BASE,
            "limiar_breakout": LIMIAR_BREAKOUT, "min_alvos_eficiencia": MIN_ALVOS_EFICIENCIA,
            "fontes": ["nflverse via nflreadpy (load_draft_picks, load_combine, load_player_stats)",
                       "College Football Data API (/draft/picks, /stats/player/season)"],
            "n_validacao": int(validos.sum()),
            "n_sem_gsis": int(passados["gsis_id"].null_count()),
            "n_eficiencia": int(com_alvos.sum()),
            "metade": metade,
        },
        "indicadores": INDICADORES, "descartados": DESCARTADOS,
        "jogadores": jogadores,
        "validacao": validacao,
        "benchmark_ranking_pre_draft": benchmark,
        "cobertura": cobertura_por_ano(wr),
        "nao_testou": quem_nao_testou(passados.filter(pl.col("jardas").is_not_null())),
    }
    SAIDA.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(dados, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    (SAIDA / "wr.json").write_text(texto, encoding="utf-8")
    (SAIDA / "wr.js").write_text(f"window.DADOS = {texto};\n", encoding="utf-8")

    base = validacao[PESOS_ATLETICOS.index(PESO_BASE)]["passados"]
    print(f"{len(jogadores)} WRs ({wr['season'].min()}–{wr['season'].max()}); validação com {validos.sum()} "
          f"(sem gsis_id: {dados['meta']['n_sem_gsis']})")
    for nome, m in base.items():
        print(f"  {nome:<34} {m['valor']:+.3f}  IC95 [{m['ic95'][0]:+.3f}, {m['ic95'][1]:+.3f}]  n={m['n']}")
    print(f"  ranking pré-Draft CFBD x desfecho  {benchmark['valor']:+.3f}  n={benchmark['n']}")
    print(f"Saída: {SAIDA / 'wr.json'}")


if __name__ == "__main__":
    main()
