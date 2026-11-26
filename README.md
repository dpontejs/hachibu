# Hachibu

Coach pessoal de treino, corrida e dieta com agentes de IA. Projeto final de IA Agêntica (2026.2).

**No ar:** https://hachibu.diegoponte.dev (cadastro com código de convite)

O relatório técnico completo (problema, arquitetura, comparação entre workflow, agente único e multiagente, avaliação) entra aqui ao fim do projeto. O design está em [`docs/features/hachibu.md`](docs/features/hachibu.md).

## Estado atual

- Conta com convite, perfil e metas diárias por fórmula (Mifflin-St Jeor ou Katch-McArdle), ou a meta prescrita por nutricionista, com a origem sempre visível.
- Diagnóstico inicial: taxa basal, gasto diário, relação cintura/altura e metas, cada um explicado.
- Tela Hoje: saldo de kcal e macros, água e refeições do dia.
- Registro de refeições com busca na TACO e gramas; os macros são calculados no servidor.
- PWA instalável no iPhone, com layout de celular e de computador.

## Fontes de dados

- **TACO**: NEPA-UNICAMP. *Tabela Brasileira de Composição de Alimentos*, 4ª ed. rev. e ampl. Campinas: NEPA-UNICAMP, 2011. A reprodução é permitida com citação da fonte. O app usa 593 dos 597 alimentos: os 4 sem valor de energia na tabela ficam de fora. A conversão parte do JSON de [marcelosanto/tabela_taco](https://github.com/marcelosanto/tabela_taco) (MIT) e está em [`scripts/gerar_taco_csv.py`](scripts/gerar_taco_csv.py); o resultado fica em `src/hachibu/data/taco.csv`.

## Como rodar

```bash
make install
cp .env.example .env   # preencha SESSION_SECRET e INVITE_CODE
make test              # back (pytest) e front (vitest)
make dev               # API em :8000 e front em :5173
docker compose up --build   # a imagem de produção, local
```
