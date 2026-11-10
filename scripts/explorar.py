"""Visualização rápida dos datasets brutos (CFBD + nflverse).

Uso: uv run scripts/explorar.py [ANO]
"""

import os
from pathlib import Path
import sys

import nflreadpy as nfl
import polars as pl
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")  # console do Windows (cp1252) não imprime as bordas das tabelas
ANO = int(sys.argv[1]) if len(sys.argv) > 1 else 2024
CFBD_URL = "https://api.collegefootballdata.com"

pl.Config(tbl_cols=-1, tbl_rows=10, fmt_str_lengths=30)  # mostra todas as colunas


def ver(nome: str, df: pl.DataFrame) -> None:
    print(f"\n===== {nome}: {df.height} linhas x {df.width} colunas =====")
    print(df.schema)
    print(df.head())


def cfbd(endpoint: str, **params) -> pl.DataFrame:
    resp = requests.get(
        f"{CFBD_URL}{endpoint}",
        params=params,
        headers={"Authorization": f"Bearer {CHAVE}"},
        timeout=60,
    )
    resp.raise_for_status()
    return pl.DataFrame(resp.json(), infer_schema_length=None)


load_dotenv(Path(__file__).parents[1] / ".env")  # .env fica na raiz do repo
CHAVE = os.getenv("CFBD_API_KEY")
if not CHAVE:
    sys.exit("CFBD_API_KEY vazia: preencha o arquivo .env")

# ---------- College Football Data ----------
draft_cfbd = cfbd("/draft/picks", year=ANO)
ver("CFBD draft picks (todas as posições)", draft_cfbd)

rec_longo = cfbd("/stats/player/season", year=ANO, category="receiving")
ver("CFBD recepção — formato longo, como vem da API", rec_longo)

# Uma linha por jogador, uma coluna por estatística (só se o schema for o esperado)
esperadas = {"playerId", "player", "team", "conference", "statType", "stat"}
if esperadas <= set(rec_longo.columns):
    rec_largo = rec_longo.with_columns(pl.col("stat").cast(pl.Float64, strict=False)).pivot(
        on="statType", index=["playerId", "player", "team", "conference"], values="stat"
    )
    ordem = "YDS" if "YDS" in rec_largo.columns else rec_largo.columns[-1]
    ver("CFBD recepção — uma linha por jogador", rec_largo.sort(ordem, descending=True))
else:
    print(f"\n[pivot pulado] colunas ausentes: {esperadas - set(rec_longo.columns)}")

# ---------- nflverse ----------
draft_nfl = nfl.load_draft_picks([ANO])
ver("nflverse draft picks (todas as posições)", draft_nfl)
if "position" in draft_nfl.columns:
    ver("nflverse draft picks WR", draft_nfl.filter(pl.col("position") == "WR"))
