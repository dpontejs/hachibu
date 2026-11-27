# Hachibu

Coach pessoal de treino, corrida e dieta com IA: um agente com skills por domínio (nutrição, musculação, corrida) que lê e atualiza o seu dia, sempre pedindo aprovação antes de mudar metas ou planos.

**No ar:** https://hachibu.diegoponte.dev (cadastro com código de convite)

O design, as decisões e as próximas etapas estão em [`docs/features/hachibu.md`](docs/features/hachibu.md).

## Estado atual

- Conta com convite, perfil e metas diárias por fórmula (Mifflin-St Jeor ou Katch-McArdle), ou a meta prescrita por nutricionista, com a origem sempre visível.
- Diagnóstico inicial: taxa basal, gasto diário, relação cintura/altura e metas, cada um explicado.
- Tela Hoje: saldo de kcal e macros, água e refeições do dia.
- Registro de refeições com busca na TACO e gramas; os macros são calculados no servidor.
- PWA instalável no iPhone, com layout de celular e de computador.
- Coach com IA no painel: conversa, foto do prato, registros e ajuste de meta com aprovação.

## Como o coach funciona

- **Agente único** (`create_agent` do LangChain com o Gemini 3.6 Flash). O estado do aluno é compartilhado entre dieta, treino e corrida, e um agente só raciocina sobre tudo junto, sem perder contexto entre especialistas.
- **Skills por domínio** (`src/hachibu/coach/skills/*/SKILL.md`: nutrição, musculação, corrida). O catálogo fica no prompt de sistema, e o coach carrega a skill do assunto com a tool `carregar_skill`. Uma pergunta mista carrega duas.
- **Tools** (`src/hachibu/coach/tools.py`) sobre funções puras (`ferramentas.py`). O usuário vem da sessão e nunca aparece no schema que o modelo vê. As calorias sempre vêm da TACO.
- **Foto do prato:** o modelo de visão lista os itens e estima as gramas, e cada item é casado com a TACO. O coach mostra a lista e só registra depois que o aluno confirma. A foto não é guardada, e o texto escrito nela é tratado como dado.
- **Aprovação humana:** `ajustar_metas` valida a proposta em código (piso, déficit de no máximo 25%, macros coerentes) e só então pausa com `interrupt()`. A conversa fica salva num checkpointer SQLite até o aluno aprovar ou recusar.
- **Robustez:** o grafo tem teto de passos por mensagem, o Gemini tem timeout de 30 s, há cota diária por usuário, tool calls que ficaram sem resposta são remendadas e o app segue funcionando sem a chave (o coach responde 503).
- **Testes:** um modelo falso com respostas roteirizadas roda no CI, e conversas reais com o Gemini ficam em `pytest -m llm`, rodadas à mão.

## Fontes de dados

- **TACO**: NEPA-UNICAMP. *Tabela Brasileira de Composição de Alimentos*, 4ª ed. rev. e ampl. Campinas: NEPA-UNICAMP, 2011. A reprodução é permitida com citação da fonte. O app usa 593 dos 597 alimentos: os 4 sem valor de energia na tabela ficam de fora. A conversão parte do JSON de [marcelosanto/tabela_taco](https://github.com/marcelosanto/tabela_taco) (MIT) e está em [`scripts/gerar_taco_csv.py`](scripts/gerar_taco_csv.py); o resultado fica em `src/hachibu/data/taco.csv`.

## Créditos de arte

- **Cerejeira da landing**: pixel art de [Infallible](https://infallible.itch.io/pack-of-sakura-trees), recolorida para a paleta verde do Hachibu (`web/public/sprites/`). As pétalas animadas são desenhadas pelo app.

## Como rodar

```bash
make install
cp .env.example .env   # preencha SESSION_SECRET, INVITE_CODE e GEMINI_API_KEY
make test              # back (pytest) e front (vitest)
make dev               # API em :8000 e front em :5173
docker compose up --build   # a imagem de produção, local
```
