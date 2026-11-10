"""Visualizador dos datasets brutos (CFBD + nflverse).

Uso: uv run streamlit run scripts/ver_dados.py
"""

import os
from pathlib import Path

import nflreadpy as nfl
import polars as pl
import requests
import streamlit as st
from dotenv import load_dotenv

CFBD_URL = "https://api.collegefootballdata.com"

load_dotenv(Path(__file__).parents[1] / ".env")  # .env fica na raiz do repo
CHAVE = os.getenv("CFBD_API_KEY")


# A CFBD tem cota mensal: cache em disco dentro da sessão do Streamlit evita rebaixar a cada clique
@st.cache_data(persist="disk", show_spinner="Baixando da CFBD...")
def cfbd(endpoint: str, **params) -> pl.DataFrame:
    resp = requests.get(
        f"{CFBD_URL}{endpoint}",
        params=params,
        headers={"Authorization": f"Bearer {CHAVE}"},
        timeout=60,
    )
    resp.raise_for_status()
    return pl.DataFrame(resp.json(), infer_schema_length=None)


@st.cache_data(show_spinner="Baixando do nflverse...")
def draft_nfl(ano: int) -> pl.DataFrame:
    return nfl.load_draft_picks([ano])


def pivot_recepcao(longo: pl.DataFrame) -> pl.DataFrame | None:
    esperadas = {"playerId", "player", "team", "conference", "statType", "stat"}
    if not esperadas <= set(longo.columns):
        return None
    return longo.with_columns(pl.col("stat").cast(pl.Float64, strict=False)).pivot(
        on="statType", index=["playerId", "player", "team", "conference"], values="stat"
    )


def mostrar(df: pl.DataFrame) -> None:
    st.caption(f"{df.height} linhas x {df.width} colunas")
    st.dataframe(df, width="stretch", height=500)
    with st.expander("Schema"):
        st.dataframe(
            pl.DataFrame({"coluna": df.columns, "tipo": [str(t) for t in df.dtypes],
                          "% nulos": [round(100 * df[c].null_count() / max(df.height, 1), 1) for c in df.columns]}),
            width="stretch",
        )


st.set_page_config(page_title="Filtro de Promessas — dados", layout="wide")
st.title("Filtro de Promessas — datasets brutos")

ano = st.sidebar.number_input("Temporada / draft", min_value=2004, max_value=2026, value=2024, step=1)
so_wr = st.sidebar.checkbox("Só WRs nos drafts", value=True)

aba_draft_cfbd, aba_rec, aba_draft_nfl = st.tabs(
    ["CFBD — draft picks", "CFBD — recepção", "nflverse — draft picks"]
)

with aba_draft_cfbd:
    if not CHAVE:
        st.error("CFBD_API_KEY vazia: preencha o arquivo .env")
    else:
        df = cfbd("/draft/picks", year=int(ano))
        if so_wr and "position" in df.columns:
            df = df.filter(pl.col("position").str.contains("(?i)wide receiver|^WR$"))
        mostrar(df)

with aba_rec:
    if CHAVE:
        longo = cfbd("/stats/player/season", year=int(ano), category="receiving")
        largo = pivot_recepcao(longo)
        if largo is None:
            st.warning("Colunas esperadas ausentes; mostrando o formato longo.")
            mostrar(longo)
        else:
            if "YDS" in largo.columns:
                largo = largo.sort("YDS", descending=True, nulls_last=True)
            mostrar(largo)
            with st.expander("Formato longo (como vem da API)"):
                mostrar(longo)

with aba_draft_nfl:
    df = draft_nfl(int(ano))
    if so_wr and "position" in df.columns:
        df = df.filter(pl.col("position") == "WR")
    mostrar(df)
