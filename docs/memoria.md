# Memória de Projeto — Etapa II: Filtro de Promessas

**Disciplina:** Visualização de Dados (PSAE00218), UFPB · **Professor:** Jorge Henrique Norões Viana
**Equipe:** Pedro Veloso, Vítor Batista, Ricardo César · **Dados gerados em:** 10/11/2026

> **Nota para a equipe (apagar antes de exportar):** o PDF do template (itens a–h) e a memória em Power BI não estavam na pasta do projeto. As seções abaixo seguem a ordem que o plano da Etapa II descreve. Antes de exportar, confira os títulos com o template, renumere como a) a h) e preencha os trechos marcados **[PENDENTE]**. Para o PDF: imprima `docs/memoria.md` (ou o HTML gerado a partir dele) desmarcando "Cabeçalhos e rodapés" na caixa de impressão do navegador.

---

## 1. Problema, persona e pergunta de decisão

**Persona.** Diretor de Scouting Universitário de uma franquia da NFL. Decide em quais Wide Receivers (WR) gastar escolhas do Draft e precisa de uma segunda opinião, baseada em dados, ao lado do trabalho de vídeo dos olheiros.
**[PENDENTE: fontes que sustentam as atribuições da persona, cobradas pelo professor. Estavam na memória anterior.]**

**Pergunta de decisão.** Como este WR se compara a WRs draftados antes, em perfil atlético e em produção universitária ajustada à oportunidade? E o quanto esse tipo de perfil se traduziu em produção nas 3 primeiras temporadas na NFL?

**Ação que o produto apoia.** Priorizar quem estudar mais a fundo e quem reavaliar quando a nota diverge do consenso do mercado. O produto não diz quem draftar.

## 2. Recorte: por que só WR

O professor pediu para consolidar o recorte por posição e justificar fórmulas, pesos e especificidades de cada posição. As métricas não se transferem entre posições: WR tem métricas de produção maduras (fatia das jardas do time, idade de breakout), a linha ofensiva quase não tem estatística individual e os defensores dependem de pressões e sacks, que têm outra literatura. Fundamentar dez posições com três pessoas daria uma tabela rasa em todas. **Só WR é apresentado como validado.** O código separa a configuração dos indicadores (`pipeline/indicadores.py`) do resto, então RB e TE podem entrar depois como demonstração da arquitetura.

## 3. Dados e tratamento

| Fonte | O que usamos | Acesso |
| --- | --- | --- |
| nflverse, `load_draft_picks` | WRs draftados, pick, idade no Draft (`age`), IDs `pfr_player_id` e `gsis_id` | `nflreadpy` |
| nflverse, `load_combine` | altura, peso, 40 jardas, salto vertical, 3-cone | `nflreadpy` |
| nflverse, `load_player_stats` | jardas e alvos por semana, só temporada regular | `nflreadpy` |
| CFBD, `/draft/picks` | ID universitário (`collegeAthleteId`), conferência, altura listada, ranking pré-Draft | API, chave gratuita |
| CFBD, `/stats/player/season` (receiving) | jardas, recepções e TDs por temporada universitária | API |

**Pipeline reproduzível.** Um comando (`uv run python -m pipeline`) baixa os dados, guarda o bruto em `data/raw/` (cache), calcula indicadores e validação e grava `web/data/wr.json`, que o HTML lê. O bruto não é versionado: é regenerável, e a CFBD exige chave pessoal. O processado é versionado para o HTML abrir sem chave.

**Ligação entre bases, sempre por ID.**
- Draft ↔ Combine: por `pfr_id` (presente para todos os 547 WRs de 2010 em diante). O código ainda tem um plano B por ano + pick, conferindo a posição, porque casar só por ano + pick trazia jogadores errados em 6 casos de 2005–2025 (TE, FB, RB e um punter).
- Draft ↔ CFBD: por ano + pick geral, buscando entre todas as posições da CFBD. Ela às vezes lista como CB ou RB quem o PFR chama de WR (ex.: Travis Hunter, 2025).
- CFBD draft ↔ estatísticas universitárias: por `collegeAthleteId`. Esse ID só casa a partir do Draft de 2010, e por isso **a base começa em 2010**: 547 WRs draftados de 2010 a 2026.
- Draft ↔ NFL: por `gsis_id`.

**Tratamentos explícitos.**
- **Teste não realizado** fica nulo, com o status "não testou" (foi ao Combine e pulou o teste) ou "não testou (não foi ao Combine)". Nunca recebe o valor mínimo nem a média.
- **2021** não teve Combine presencial. A base do Combine traz 63 WRs naquele ano (40–55 nos vizinhos), e 95% deles têm 40 jardas. Entre os WRs *draftados* em 2021, a cobertura é de 71%. O padrão sugere tempos de Pro Day (confiança moderada). Os testes de 2021 ficam marcados, e a tela avisa.
- **Altura** sem medição no Combine usa a altura listada pela CFBD, marcada como "listada".
- **Fatia das jardas do time:** jardas do jogador ÷ soma das jardas de todos os recebedores do time na mesma base. Conferimos que essa soma bate com as jardas aéreas do time na CFBD (razão média de 1,000 em 2023). Quem não jogou o último ano (ex.: opt-out em 2020, como Ja'Marr Chase) usa a temporada anterior, com aviso.
- **Idade de breakout:** idade aproximada na primeira temporada com 20% ou mais das jardas do time. A aproximação é a idade no Draft menos os anos até o Draft; a idade é inteira. Quem nunca chegou a 20% recebe a pior posição, porque é um resultado e não dado faltante.

**Cobertura** (% dos WRs draftados, tabela completa na tela de Validação): 40 jardas entre 65% e 81% de 2016 a 2025; 3-cone entre 20% e 23% de 2023 a 2025 (por isso fica fora da nota); produção universitária entre 82% e 100% por classe; `gsis_id` faltando para 3 dos 445 WRs de 2010–2023. Em 2026 a base do Combine parece incompleta (47% com 40 jardas).

## 4. Indicadores e fundamentação

Cada indicador vira percentil entre os WRs draftados de 2010 a 2023 (o grupo de comparação). Nas idades, menor é melhor, então o percentil é invertido. Assim, "para fora = melhor" em todos os eixos.

| Indicador | Bloco | Origem | Fonte | Peso no bloco | Justificativa do peso |
| --- | --- | --- | --- | --- | --- |
| Altura | atlético | Literatura | Teramoto, Cross & Willick (2016), JSCR 30(5) (verificação secundária) | 1/3 | A literatura aponta altura e vertical para WR, mas não dá pesos relativos; dividimos igualmente |
| Salto vertical | atlético | Literatura | Teramoto et al. (2016); Jensen & Mulholland, CHANCE (ano e volume a confirmar) | 1/3 | Idem |
| Speed Score: peso × 200 / (40 jardas)⁴ | atlético | Prática de mercado | Bill Barnwell (autoria a confirmar) | 1/3 | Velocidade ajustada pelo peso |
| Fatia das jardas do time (último ano) | produção | Literatura + prática | Jensen & Mulholland; dominator rating (RotoViz, PlayerProfiler) | 1/2 | Única métrica de produção com apoio acadêmico; mede oportunidade, não volume |
| Idade de breakout | produção | Prática de mercado | RotoViz; limiar de 20% da PlayerProfiler (a RotoViz usa 30%) | 1/4 | Divide o restante com a idade no Draft: as duas medem precocidade, e meio bloco para cada uma contaria idade duas vezes |
| Idade no Draft | produção | Prática de mercado | Sharp Football (2020), early declare | 1/4 | Idem |
| Nota composta e peso entre blocos | — | Proposta da equipe | este relatório | base 20% atlético | Kuzmits & Adams (2008) e Vincent et al. (2019) acham poder preditivo fraco a modesto do Combine para WR; a validação (seção 8) confirma |

**Ficaram de fora:** 3-cone (cobertura baixa), 40 jardas isolada (já entra no Speed Score), totais de jardas, TDs e recepções (medem volume, não oportunidade) e yards per route run (sem dado gratuito).

**Como a nota é montada.** (1) Média ponderada dos percentis disponíveis em cada bloco. Indicador sem dado sai da média e os pesos dos outros são reescalados. (2) Mistura dos blocos pelo peso atlético. Se um bloco inteiro faltar, a nota usa só o outro. (3) A mistura vira percentil de novo no grupo de comparação. Para cada jogador, o pipeline calcula também a **faixa** do que a nota seria se os indicadores ausentes tivessem qualquer resultado (todos no percentil 0 ou todos no 100).

## 5. Medidas calculadas

Com aprovação do professor, as medidas saem do DAX e passam para Python (pipeline) e JavaScript (interface):

| Medida | Onde | Regra |
| --- | --- | --- |
| Percentil de cada indicador | `indicadores.percentil` | contra o grupo 2010–2023; empate conta meio; nulo continua nulo |
| Nota composta | `indicadores.notas` | seção 4, calculada para os pesos de 0% a 50% |
| Faixa por teste ausente | `indicadores.notas(..., preencher=0/100)` | mínimo e máximo possíveis |
| Desfecho na NFL | `__main__.janela_nfl` | jardas na temporada regular nas temporadas do Draft até +2; com `gsis_id` e sem linha = 0 |
| Spearman, Spearman parcial, resíduo | `validacao.py` | seção 8 |
| Intervalo de 95% | `validacao.com_intervalo` | bootstrap de jogadores, 1.000 reamostras, semente fixa |
| Mudanças no top 10 por cenário | `app.js`, `mudancasTop10` | jogadores no top 10 do cenário que não estão no top 10 da base |
| Perfil semelhante | `app.js`, `vizinhos` | WRs 2010–2023 com nota a até 5 pontos: quartis de jardas e % acima de 2.000 |

As regras de negócio têm testes automáticos (`uv run pytest`): o teste ausente não vira valor, quem nunca jogou tem desfecho 0, a direção dos percentis e o Spearman.

## 6. Visualizações

HTML estático em JavaScript puro e SVG, sem bibliotecas externas: abre com duplo clique e funciona offline. Paleta com tema claro e escuro, validada para daltonismo nos dois slots usados (azul = nota, laranja = destaque ou coorte recente). Cinza é reservado para "não testou". Testado com Playwright em 1280 px e 390 px (celular), sem rolagem horizontal e sem erros no console.

1. **Ranking.** Uma classe do Draft por vez. Barras horizontais com o percentil composto, faixa clara do que mudaria com os testes ausentes, linha da mediana (50) e etiqueta "N indicadores sem dado". O texto fixo diz o grupo de comparação. Barras foram escolhidas porque a tarefa é comparar magnitudes numa lista ordenada.
2. **Perfil.** Radar de seis eixos em percentis (para fora = melhor), com anel tracejado na mediana. Eixo sem teste aparece tracejado em cinza com "não testou". Com algum eixo faltando, o radar não desenha área: só liga eixos vizinhos medidos, para o vazio não parecer valor baixo. Ao lado ficam a nota, a faixa, o "perfil semelhante" (distribuição de produção de WRs com nota parecida) e a tabela com valor bruto, percentil e situação de cada indicador.
3. **Validação.** Indicadores-chave com IC de 95%. Duas dispersões: nota × pick real (log) e nota × produção, com alternância para "jardas acima do esperado pelo pick" e as maiores discrepâncias rotuladas. Tabelas de discrepâncias, de "quem não testou" e de cobertura por classe.
4. **Metodologia.** Tabela de fundamentação (lida do mesmo `wr.json`, sem cópia manual), descartados, regras de dados, limites e fontes.

## 7. Parâmetro e cenários

O "corte de 40 jardas" da versão anterior foi substituído pelo **peso do perfil atlético na nota**, de 0% a 50% em passos de 10. Há três cenários com botão:

| Cenário | Peso atlético | Mudanças no top 10 vs. base (média por classe, 2010–2026) |
| --- | --- | --- |
| Só produção | 0% | 1,2 |
| Base | 20% | — |
| Atlético | 40% | 1,8 |

Os botões mostram quantos jogadores entram no top 10 da classe selecionada em relação à base (em 2026: 1 no cenário só produção, 3 no atlético). O parâmetro funciona como análise de sensibilidade dos pesos: o top 10 é estável, e a validação piora quando o peso atlético sobe (seção 8).

## 8. Validação retrospectiva

**Coorte de validação:** 442 WRs draftados de 2010 a 2023 (3 sem `gsis_id` excluídos). **Desfecho:** jardas recebidas na temporada regular nas 3 primeiras temporadas, com 0 para quem nunca jogou. Janela fixa, igual para todas as classes. **Classes recentes (2024–2026, 102 WRs):** só comparação com o pick.

Resultados no peso base (20%), Spearman com IC de 95% por bootstrap:

| Comparação | Valor | IC 95% |
| --- | --- | --- |
| Nota × produção | +0,36 | +0,27 a +0,44 |
| Pick real × produção (referência) | +0,63 | +0,58 a +0,68 |
| **Nota × produção, descontado o pick (Spearman parcial)** | **+0,15** | **+0,07 a +0,24** |
| Nota × jardas acima do esperado pelo pick | +0,12 | +0,03 a +0,21 |
| Nota × pick real | +0,40 | +0,31 a +0,48 |
| Nota × jardas por alvo (secundário; 257 WRs com 50+ alvos) | +0,04 | −0,09 a +0,16 |
| Ranking pré-Draft da CFBD × produção (benchmark; n = 387) | +0,57 | +0,49 a +0,64 |
| Nota × pick, classes 2024–2026 | +0,48 | +0,31 a +0,62 |

**Leitura.**
1. O pick real ordena a produção muito melhor que a nota. Isso era esperado: o mercado tem vídeo, exames e entrevistas, e pick alto recebe mais alvos.
2. Descontado o pick, a nota mantém um sinal **pequeno e positivo** (+0,15). Esse é o valor que o produto acrescenta: uma segunda opinião, não um substituto do Draft.
3. A nota não prevê eficiência (jardas por alvo) entre quem jogou. Ela ordena volume de produção, não qualidade por alvo.

**Sensibilidade ao peso atlético** (Spearman parcial): 0% +0,17 · 10% +0,16 · 20% +0,15 · 30% +0,13 · 40% +0,11 · 50% +0,08. Mais peso atlético piora a nota, o que é coerente com a literatura do Combine.

**Estabilidade no tempo e calibração sem vazamento.** Spearman parcial no peso base: +0,20 nos Drafts 2010–2016 e +0,11 nos de 2017–2023. O IC da segunda metade inclui zero, então o sinal pode estar enfraquecendo. Se escolhêssemos o peso só com 2010–2016, o melhor seria 0% atlético. Aplicado a 2017–2023, ele dá +0,12, contra +0,11 no peso base: diferença desprezível. **Mantivemos 20% como escolha declarada** (o template pede um parâmetro com efeito visível), e a tela mostra que 0–10% teria validação igual ou levemente melhor.

**Maiores discrepâncias** (percentil da nota × percentil de jardas acima do esperado pelo pick):
- **Nota acima da produção:** N'Keal Harry (2019, pick 32), Corey Davis (2017, pick 5), Breshad Perriman (2015, pick 26), Stephen Hill (2012, pick 43), A.J. Jenkins (2012, pick 30). Todos produziram muito no college, foram picks altos e renderam pouco nas 3 primeiras temporadas. Lesões (Davis, Perriman) e contexto de ataque não entram na nota. [Investigar caso a caso antes da apresentação.]
- **Produção acima da nota:** Tyreek Hill (2016, pick 165), Hunter Renfrow (2019, pick 149), Terry McLaurin (2019, pick 76), John Brown (2014, pick 91), Jeremy Kerley (2011, pick 153). Hill é o caso-limite: seu último ano foi na Divisão II (West Alabama), fora da CFBD. A nota usou 2014, em Oklahoma State, quando ele era principalmente RB e retornador. McLaurin dividia as jardas num ataque com vários WRs draftados, e a fatia das jardas pune isso.

**Quem não fez os testes não é aleatório** (2010–2023):

| Teste | Grupo | WRs | Pick mediano | % 1ª rodada | Jardas medianas |
| --- | --- | --- | --- | --- | --- |
| 40 jardas | testou | 355 | 107 | 12,7 | 562 |
| 40 jardas | não testou | 87 | 186 | 11,5 | 258 |
| Salto vertical | testou | 335 | 109 | 13,1 | 568 |
| Salto vertical | não testou | 107 | 175 | 10,3 | 377 |

Quem pula o teste foi, em mediana, draftado mais tarde e produziu menos. A proporção de 1ª rodada é parecida nos dois grupos, então o grupo que não testou mistura prospectos de topo que dispensam o teste e atletas sem convite ou lesionados. Imputar o mínimo, como fazia a versão anterior, puniria igualmente os dois casos. Por isso o "não testou" fica visível, e a nota mostra a faixa.

## 9. Teste com usuário

**[PENDENTE: refazer o teste.]** A versão anterior relatou que "o olhar foi para o radar", o que não mostra se o produto funciona. Protocolo proposto, com 3 ou mais pessoas:

1. "Na classe de 2026, quem tem a maior nota e quantos indicadores dele não foram medidos?"
2. "Abra o perfil de Marvin Harrison Jr. e diga quais testes ele não fez e quanto a nota poderia mudar."
3. "No cenário só produção, quantos jogadores mudam no top 10 de 2026?"
4. "A nota acerta mais ou menos que o pick real? Onde você viu isso?"

Registrar, para cada tarefa, se a pessoa concluiu, quanto tempo levou e onde travou. Relatar o que ela conseguiu ou não fazer, e não para onde olhou.

## 10. Ética e linguagem

- Nenhum rótulo definitivo ("bust", "elite", "evitar"). A tela fala em percentil, faixa e "perfil semelhante a…".
- O grupo de comparação aparece em todas as telas ("entre WRs draftados de 2010 a 2023").
- A incerteza é visível: a faixa por teste ausente no ranking, o IC de 95% na validação e a dispersão de produção dos perfis semelhantes.
- Os limites são declarados na tela de Metodologia: a nota não vê lesões, entrevistas, vídeo, esquema, quarterback, força das defesas nem contexto do time. WRs de escolas fora da CFBD ou vindos de junior college têm produção incompleta. A ferramenta não avalia quem não foi draftado.

## Correções em relação à memória anterior

| Correção obrigatória | Como ficou |
| --- | --- |
| "A base não possui idade" | Errado: `age` existe para quase todos os WRs desde 2008 e é usada direto. A engenharia reversa a partir do ano do Draft foi removida |
| Imputação de teste faltante pelo mínimo | Removida. O status é "não testou", com cobertura reportada e faixa na nota |
| Join por `player_name` | Join por ID: `pfr_id`, `collegeAthleteId` e `gsis_id` (seção 3) |
| IEA dividido pelo máximo de todas as posições | Percentil dentro de WR, no grupo 2010–2023 |
| DP em jardas brutas | Fatia das jardas do time (por oportunidade) |
| Cenário 2 "realça atletas mais pesados" | Removido junto com o corte de 40 jardas; os cenários agora variam o peso atlético |
| JPPT descrita como "das demais posições" | O indicador saiu; jardas por alvo entra só como desfecho secundário de WR |
| Teste com usuário baseado em "o olhar foi para o radar" | Protocolo por tarefas (seção 9) [PENDENTE executar] |
| "Corte de Risco" e "Elite Speed" | Removidos. O produto voltou a se chamar "Filtro de Promessas" (Draft não é contratação) |
| PDF com cabeçalho de impressão | Exportar sem "Cabeçalhos e rodapés" (nota no topo) |

## Discussão final

**O que o produto entrega.** Uma posição relativa honesta. Cada WR é comparado ao mesmo grupo de WRs draftados, com os testes ausentes visíveis e a incerteza mostrada, e cada indicador tem origem e fonte declaradas.

**O que a validação mostrou.** O Draft é difícil de bater: o pick real tem correlação de +0,63 com a produção, e a nota, +0,36. A nota acrescenta um sinal pequeno e positivo descontado o pick (+0,15). Esse sinal enfraquece nos Drafts mais recentes, e seu intervalo passa a incluir zero. O perfil atlético atrapalha mais do que ajuda, como a literatura do Combine sugeria. O resultado, inclusive a parte negativa, está na tela de Validação.

**Limites.** (1) Pesos declarados, não estimados. (2) A idade de breakout é aproximada por idades inteiras e perde temporadas fora da CFBD (Divisão II, junior college), o que favorece quem jogou sempre na FBS. (3) A fatia das jardas não ajusta pela força da conferência: um WR da FCS pode dominar um ataque fraco. (4) A janela de 3 temporadas mistura temporadas de 16 e 17 jogos (classes de 2021 em diante têm até 3 jogos a mais). (5) O desfecho em jardas ainda carrega a oportunidade; o Spearman parcial e o resíduo atenuam isso, mas não eliminam.

**Próximos passos.** Ajuste pela força das defesas e conferências, ajuste dos tempos de Pro Day, incerteza por bootstrap no próprio ranking, jogadores comparáveis por vizinhos mais próximos, extensão para RB e TE com a mesma arquitetura e teste de usabilidade com tarefas.

## Referências

Todas vêm do plano da Etapa II, com o status de verificação registrado lá. Itens "a confirmar" precisam ser checados antes da entrega.

- Kuzmits & Adams (2008). The NFL Combine: does it predict performance in the National Football League? *Journal of Strength and Conditioning Research*, 22. (número da edição diverge entre fontes)
- Teramoto, Cross & Willick (2016). *Journal of Strength and Conditioning Research*, 30(5). doi:10.1519/JSC.0000000000001202 (verificação secundária)
- Vincent, Blissmer & Hatfield (2019). *Journal of Strength and Conditioning Research*, 33(1), 104–111.
- Jensen & Mulholland. *CHANCE* (WR e TE). Ano e volume a confirmar.
- Mulholland & Jensen (2014). *Journal of Quantitative Analysis in Sports*, 10(4).
- Massey & Thaler (2013). *Management Science*, 59(7), 1479–1495.
- Brill & Wyner (2026). *The American Statistician*, 80(1), 15–30.
- Hendricks, DeBrock & Koenker (2003). *Journal of Labor Economics*, 21(4), 857–886.
- Prática de mercado (sem revisão por pares): RotoViz (breakout age, dominator rating), PlayerProfiler (limiar de 20%), Sharp Football Analysis (2020, early declare), Bill Barnwell (Speed Score, autoria a confirmar).
- Dados: nflverse (`nflreadpy`) e College Football Data API.
