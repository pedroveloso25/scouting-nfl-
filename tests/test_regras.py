"""Regras de negócio que não podem quebrar em silêncio (CLAUDE.md, "Regras de dados")."""

import math

import numpy as np
import polars as pl

from pipeline.__main__ import janela_nfl
from pipeline.indicadores import INDICADORES, notas, percentil
from pipeline.validacao import spearman, spearman_parcial

NAN = np.nan


def test_percentil_inverte_quando_menor_e_melhor():
    ref = np.array([20.0, 21, 22, 23])
    assert percentil(np.array([20.0]), ref, maior_melhor=False)[0] > percentil(np.array([23.0]), ref, False)[0]
    assert percentil(np.array([23.0]), ref, maior_melhor=True)[0] == 87.5  # 3 abaixo + meio empate de 4


def test_teste_nao_realizado_continua_nulo():
    ref = np.array([1.0, 2, 3])
    assert np.isnan(percentil(np.array([NAN]), ref, True)[0])


def test_nunca_atingiu_breakout_fica_com_a_pior_posicao():
    ref = np.array([19.0, 20, 21, math.inf])
    assert percentil(np.array([math.inf]), ref, maior_melhor=False)[0] == 12.5


def _pcts(**valores):
    base = {i["id"]: np.array([NAN]) for i in INDICADORES}
    base.update({k: np.array([v]) for k, v in valores.items()})
    return base


def test_nota_ignora_faltante_em_vez_de_imputar_minimo():
    # Só altura medida no bloco atlético: o bloco vale a altura, não a média com zeros
    p = _pcts(altura=80.0, fatia_jardas=50.0, breakout_idade=50.0, idade_draft=50.0)
    assert notas(p, 0.2)[0] == 0.2 * 80 + 0.8 * 50


def test_faixa_cobre_o_teste_ausente_com_qualquer_resultado():
    p = _pcts(altura=80.0, fatia_jardas=50.0, breakout_idade=50.0, idade_draft=50.0)
    lo, hi = notas(p, 0.2, preencher=0)[0], notas(p, 0.2, preencher=100)[0]
    assert lo < notas(p, 0.2)[0] < hi


def test_peso_zero_ignora_o_bloco_atletico():
    p = _pcts(altura=99.0, vertical=99.0, speed_score=99.0, fatia_jardas=10.0, breakout_idade=10.0, idade_draft=10.0)
    assert notas(p, 0.0)[0] == 10.0


def test_quem_tem_id_e_nunca_jogou_tem_desfecho_zero():
    wr = pl.DataFrame({"id": ["a", "b", "c"], "season": [2020, 2020, 2020], "gsis_id": ["g1", "g2", None]})
    stats = pl.DataFrame({"player_id": ["g1", "g1", "g1"], "season": [2020, 2022, 2023], "week": [1, 1, 1],
                          "team": ["X"] * 3, "targets": [5, 5, 5], "receptions": [3, 3, 3],
                          "receiving_yards": [40.0, 60.0, 999.0], "receiving_tds": [0, 1, 0]})
    out = {r["id"]: r for r in janela_nfl(wr, stats).iter_rows(named=True)}
    assert out["a"]["jardas"] == 100  # 2023 está fora da janela 2020–2022
    assert out["b"]["jardas"] == 0 and out["b"]["jogos"] == 0
    assert out["c"]["jardas"] is None and out["c"]["sem_gsis"]


def test_spearman_e_parcial():
    x = np.array([1.0, 2, 3, 4, 5])
    assert spearman(x, x**3) == 1.0
    assert spearman(x, -x) == -1.0
    z = np.array([5.0, 1, 4, 2, 3])
    assert abs(spearman_parcial(x, x, z) - 1.0) < 1e-9
