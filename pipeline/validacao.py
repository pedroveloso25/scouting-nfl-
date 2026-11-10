"""Validação retrospectiva do ranking.

Duas perguntas, dois alvos (plano, seção 3):
- O ranking pensa parecido com o mercado? -> Spearman(nota, pick real).
- O ranking acerta quem produz na NFL? -> Spearman(nota, jardas nas 3 primeiras temporadas).

A segunda é contaminada por oportunidade: pick alto recebe mais alvos por ter sido pick alto. Por isso a
métrica que responde "o ranking acrescenta algo ao Draft?" é o Spearman PARCIAL controlando o pick,
e o resíduo do desfecho sobre log(pick). Os pesos não são calibrados nos dados (são declarados), então
não há vazamento; mesmo assim reportamos as duas metades da janela para ver se o resultado é estável.
"""

import numpy as np

N_BOOTSTRAP = 1000
SEMENTE = 42


def _postos(x: np.ndarray) -> np.ndarray:
    """Postos médios (empates recebem a média), como no Spearman clássico."""
    ordem = np.argsort(x, kind="mergesort")
    postos = np.empty(len(x))
    postos[ordem] = np.arange(1, len(x) + 1)
    _, inv, cont = np.unique(x, return_inverse=True, return_counts=True)
    soma = np.bincount(inv, weights=postos)
    return (soma / cont)[inv]


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a - a.mean(), b - b.mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / den) if den > 0 else float("nan")


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    return _pearson(_postos(x), _postos(y))


def spearman_parcial(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> float:
    """Correlação de postos entre x e y removendo a parte linear (em postos) explicada por z."""
    rxy, rxz, ryz = spearman(x, y), spearman(x, z), spearman(y, z)
    return (rxy - rxz * ryz) / np.sqrt((1 - rxz**2) * (1 - ryz**2))


def residuo_log_pick(desfecho: np.ndarray, pick: np.ndarray) -> np.ndarray:
    """Jardas acima (ou abaixo) do que o pick sozinho prevê, por mínimos quadrados em log(pick)."""
    X = np.column_stack([np.ones(len(pick)), np.log(pick)])
    coef, *_ = np.linalg.lstsq(X, desfecho, rcond=None)
    return desfecho - X @ coef


def com_intervalo(funcao, *colunas: np.ndarray) -> dict:
    """Valor pontual + intervalo de 95% por bootstrap de jogadores (reamostragem com reposição)."""
    rng = np.random.default_rng(SEMENTE)
    n = len(colunas[0])
    reps = []
    for _ in range(N_BOOTSTRAP):
        idx = rng.integers(0, n, n)
        reps.append(funcao(*(c[idx] for c in colunas)))
    lo, hi = np.nanpercentile(reps, [2.5, 97.5])
    return {"valor": round(float(funcao(*colunas)), 3), "ic95": [round(float(lo), 3), round(float(hi), 3)], "n": n}


def metricas(nota: np.ndarray, pick: np.ndarray, desfecho: np.ndarray) -> dict:
    """Bateria de métricas para uma coorte. Pick entra negativo: pick 1 é o "maior" valor de mercado."""
    return {
        "nota_x_desfecho": com_intervalo(spearman, nota, desfecho),
        "pick_x_desfecho": com_intervalo(lambda p, d: spearman(-p, d), pick, desfecho),
        "nota_x_pick": com_intervalo(lambda n, p: spearman(n, -p), nota, pick),
        "parcial_nota_desfecho_dado_pick": com_intervalo(
            lambda n, d, p: spearman_parcial(n, d, -np.log(p)), nota, desfecho, pick),
        "nota_x_residuo": com_intervalo(lambda n, d, p: spearman(n, residuo_log_pick(d, p)), nota, desfecho, pick),
    }
