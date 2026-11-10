# Filtro de Promessas — scouting de WR para o NFL Draft

Projeto da disciplina Visualização de Dados (PSAE00218, UFPB). Ajuda um Diretor de Scouting a avaliar prospectos de Wide Receiver combinando perfil atlético (Combine) com produção universitária, sempre comparados a WRs draftados de 2010 a 2023, e mostra o quanto esse perfil se traduziu em produção nas 3 primeiras temporadas na NFL.

## Abrir o produto

Abra `web/index.html` no navegador (duplo clique serve). Os dados já vêm em `web/data/`, sem precisar de chave nem de Python.

## Regenerar os dados

Requer [uv](https://docs.astral.sh/uv/) e Python 3.12.

```sh
uv sync
cp .env.example .env          # preencha CFBD_API_KEY (chave gratuita em collegefootballdata.com)
uv run python -m pipeline     # ~1 min; usa o cache de data/raw/ se existir
uv run python -m pipeline --atualizar   # baixa tudo de novo (nflverse + ~45 chamadas à CFBD)
uv run pytest                 # regras de negócio (não testou, desfecho 0, percentis, Spearman)
```

## Estrutura

```
pipeline/
  fontes.py       download e cache dos dados brutos (nflverse, CFBD)
  indicadores.py  fundamentação (origem, fonte, peso) + cálculo dos indicadores e percentis
  validacao.py    Spearman, Spearman parcial, resíduo sobre log(pick), bootstrap
  __main__.py     orquestra tudo e grava web/data/wr.json e wr.js
web/              o produto: index.html + app.js + estilo.css (sem dependências externas)
docs/memoria.md   memória da Etapa II
scripts/explorar.py  inspeção rápida dos dados brutos no terminal
tests/            testes das regras de dados
```

## O que é versionado

- **Não:** `data/raw/` (51 MB de snapshots do nflverse e respostas da CFBD). É regenerável, e a CFBD exige chave pessoal e tem cota mensal.
- **Sim:** `web/data/wr.json` e `wr.js` (~550 KB cada). Assim o HTML funciona direto de um clone ou do GitHub Pages, sem chave. O `wr.js` é o mesmo JSON numa variável global, porque o navegador bloqueia `fetch()` de arquivo local (`file://`). Custo: cada regeneração grava ~1 MB no histórico.
