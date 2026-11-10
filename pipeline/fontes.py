"""Download e cache dos dados brutos (nflverse e CFBD).

Tudo que vem de fora passa por aqui e fica salvo em data/raw/. Rodar de novo reaproveita o cache,
o que torna o pipeline reproduzível (mesmo snapshot) e poupa a cota mensal da CFBD.
Use atualizar=True para baixar tudo de novo.
"""

import json
import os
from pathlib import Path

import nflreadpy as nfl
import polars as pl
import requests
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
CFBD_URL = "https://api.collegefootballdata.com"


def _parquet(nome: str, baixar, atualizar: bool) -> pl.DataFrame:
    caminho = RAW / "nflverse" / f"{nome}.parquet"
    if caminho.exists() and not atualizar:
        return pl.read_parquet(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df = baixar()
    df.write_parquet(caminho)
    return df


def draft_picks(atualizar: bool = False) -> pl.DataFrame:
    return _parquet("draft_picks", nfl.load_draft_picks, atualizar)


def combine(atualizar: bool = False) -> pl.DataFrame:
    return _parquet("combine", nfl.load_combine, atualizar)


def player_stats(temporadas: list[int], atualizar: bool = False) -> pl.DataFrame:
    """Estatísticas semanais da NFL, só temporada regular (os playoffs premiam quem joga em time bom)."""
    def baixar():
        semanal = nfl.load_player_stats(seasons=temporadas)
        return semanal.filter(pl.col("season_type") == "REG").select(
            "player_id", "season", "week", "team", "targets", "receptions", "receiving_yards", "receiving_tds"
        )
    return _parquet(f"player_stats_reg_{min(temporadas)}_{max(temporadas)}", baixar, atualizar)


def _chave_cfbd() -> str:
    load_dotenv(RAIZ / ".env")
    chave = os.getenv("CFBD_API_KEY")
    if not chave:
        raise SystemExit("CFBD_API_KEY vazia: copie .env.example para .env e preencha a chave")
    return chave


def cfbd(endpoint: str, atualizar: bool = False, **params) -> list[dict]:
    """Uma chamada à CFBD, guardada como JSON cru (data/raw/cfbd/<endpoint>_<params>.json)."""
    sufixo = "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
    caminho = RAW / "cfbd" / f"{endpoint.strip('/').replace('/', '_')}_{sufixo}.json"
    if caminho.exists() and not atualizar:
        return json.loads(caminho.read_text(encoding="utf-8"))
    resp = requests.get(
        f"{CFBD_URL}{endpoint}",
        params=params,
        headers={"Authorization": f"Bearer {_chave_cfbd()}"},
        timeout=60,
    )
    resp.raise_for_status()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(resp.json(), ensure_ascii=False), encoding="utf-8")
    return resp.json()
