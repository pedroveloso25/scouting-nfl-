# CLAUDE.md — scouting-nfl-

## Projeto
"Filtro de Promessas" é o projeto da disciplina Visualização de Dados (PSAE00218, UFPB). A equipe é Pedro Veloso, Vítor Batista e Ricardo César; o professor é Jorge H. N. Viana.

O produto é um HTML interativo. Ele ajuda um Diretor de Scouting a avaliar prospectos de **Wide Receiver** para o NFL Draft, combinando perfil atlético (Combine) e produção universitária.

**Pergunta de decisão:** como este WR se compara a WRs draftados antes, em perfil atlético e em produção universitária ajustada à oportunidade? E o quanto esse tipo de perfil se traduziu em produção nas 3 primeiras temporadas na NFL?

## Escopo da Etapa II (prioridades do professor)
1. **Recorte:** apenas WR é apresentado como validado. A arquitetura pode ser genérica por posição.
2. **Fundamentação:** cada indicador registra origem (prática de mercado / literatura / proposta da equipe), fonte e justificativa do peso.
3. **Validação retrospectiva:**
   - Drafts até 2023: comparar com a produção nas 3 primeiras temporadas e com o pick real.
   - Drafts 2024–2026: comparar com o pick, com a cobertura do Combine reportada.
4. **Ética e linguagem:** sem rótulos definitivos ("bust", "evitar", "elite"). Sempre mostrar o grupo de comparação, a incerteza e os testes não realizados.

Fora de escopo nesta etapa: necessidades do elenco, adaptação ao Brasil e ajuste pela força das defesas adversárias. Esses temas ficam como próximos passos.

Detalhes no documento "Filtro de Promessas — Plano da Etapa II", seção "Plano de finalização".

## Regras de dados
- Join por ID (`pfr_id`/`pfr_player_id`, `cfb_player_id`, `gsis_id`), nunca por nome. Exceção: em 2026, `draft_ovr` está vazio no Combine; usar `pfr_id`.
- Teste não realizado nunca é imputado em silêncio. Ele é marcado como "não testou", e a cobertura é reportada por ano.
- Os dados de 2021 (sem Combine presencial) provavelmente são de Pro Day. Tratar explicitamente.
- Percentis são calculados dentro de WR, sempre na mesma janela de Drafts.
- Desfecho na NFL: janela fixa das 3 primeiras temporadas, a partir de `load_player_stats`, **só temporada regular** (`season_type == "REG"`; os playoffs dão jogos extras aos times bons). Não usar totais de carreira.
  - **Desfecho principal:** total na janela (ex.: jardas recebidas nas 3 temporadas). O denominador é a janela, não os jogos disputados: jogos perdidos por lesão ou banco fazem parte do desfecho.
  - **Jogador com `gsis_id` e sem nenhuma linha de estatística = desfecho 0**, nunca nulo descartado. Descartar cria viés de sobrevivência.
  - **Jogador sem `gsis_id`** (17 dos 609 WRs de 2005–2023, quase todos antes de 2010) é problema de dados: excluir da validação e reportar a contagem.
  - **Eficiência (jardas por alvo) é desfecho secundário**, com mínimo de alvos declarado e o N reportado. Não usar jardas por jogo, que favorece quem jogou pouco.
  - Confundimento por oportunidade (pick alto joga mais) não se resolve com taxa por jogo. Trate comparando com o pick: Spearman parcial controlando o pick ou resíduo sobre log(pick).
- Se calibrar pesos, separar por tempo: calibrar nos Drafts antigos e testar nos recentes.
- A chave da CFBD fica só em `CFBD_API_KEY` no `.env`. O `.env` nunca é versionado.

## Ambiente
- uv + Python 3.12. `link-mode = "copy"` é necessário porque o repositório está no OneDrive.
- Sem Streamlit. O produto final é HTML estático; exploração de dados é feita em scripts Python.

## Commits
- Mensagens em Conventional Commits, com título de até 72 caracteres e corpo explicando o porquê.
- Nunca versionar `.env`, `data/raw/` nem chaves.
