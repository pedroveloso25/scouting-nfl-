# Filtro de Promessas — scouting de WR para o NFL Draft

Projeto da disciplina Visualização de Dados (PSAE00218, UFPB). Ajuda um Diretor de Scouting a avaliar prospectos de Wide Receiver combinando perfil atlético (Combine) com produção universitária.

## Setup

Requer [uv](https://docs.astral.sh/uv/) e Python 3.12.

```sh
uv sync
cp .env.example .env   # preencha CFBD_API_KEY (chave gratuita em collegefootballdata.com)
```

## Explorar os dados brutos

```sh
uv run scripts/explorar.py 2024              # schemas e amostras no terminal
uv run streamlit run scripts/ver_dados.py    # mesmas tabelas com % de nulos por coluna
```

Fontes: nflverse (`nflreadpy`: draft picks e Combine) e a API CFBD (`/draft/picks` e `/stats/player/season`).
