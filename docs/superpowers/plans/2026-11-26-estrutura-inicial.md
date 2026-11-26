# Estrutura inicial: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hachibu no ar em `hachibu.diegoponte.dev`: cadastro com convite, login, formulário de perfil com metas por fórmula, tela Hoje com refeição manual e água, PWA instalável no iPhone e utilizável no computador.

**Architecture:** Container único. O FastAPI (`src/hachibu`) serve `/api/*` e o build do React (`web/dist`), com fallback para `index.html`. SQLite em `/data`, migrações SQL numeradas. Sessão por cookie assinado com `user_id`. Toda query filtra por `user_id`, que vem só da sessão.

**Tech Stack:** Python 3.12, uv, FastAPI, argon2-cffi, itsdangerous, pytest, ruff · Node 22, Vite, React 19, TypeScript, react-router, vitest · Docker, GitHub Actions, GHCR · infra: Compose + Caddy + Ansible + Terraform.

**Spec:** `docs/features/hachibu.md` (seções "Stack e deploy", "Contratos/Onboarding etapa 1", "Etapas", item 1). Referência de padrões: repo `~/today` (Dockerfile, CI, auth, migrações) e `~/infra/stacks/today`.

## Global Constraints

- Commits em pt-BR, conventional **sem escopo** (`feat: ...`), **sem** linha de coautoria.
- Nenhum segredo no repo: `.env` no `.gitignore`, `.env.example` com placeholders.
- `user_id` nunca vem do corpo da requisição; só de `current_user` (dependência da sessão).
- Data "de hoje" calculada no fuso `America/Sao_Paulo` (config `APP_TZ`).
- Tema A "Sutil": fundo `#12141a`, cards `#1b1e27`, acento `#7cf29a`; Press Start 2P só em rótulos, VT323 em números, Inter no texto. Fontes servidas pelo próprio app (`web/public/fonts`), sem Google Fonts em produção.
- Layout: < 1024 px navegação inferior; ≥ 1024 px barra lateral + conteúdo + painel do coach à direita (placeholder "O coach chega na próxima etapa").
- `make test` (pytest + vitest) e `make lint` (ruff + tsc) verdes antes de cada commit.

## Review Focus

1. Refeição registrada às 23h50 e às 00h10 (horário de Brasília) caem em dias diferentes, não em UTC → `test_hoje_usa_fuso_de_sao_paulo` (Task 5).
2. E-mail com caixa/espaços diferentes (`Diego@X.com `) é o mesmo usuário → `test_email_normalizado` (Task 3).
3. Usuário logado sem perfil abre o app → `/api/hoje` devolve 409 `perfil_incompleto` e o front leva ao formulário → `test_hoje_sem_perfil` (Task 5).
4. Valores absurdos no perfil (altura 0, peso 500) → 422, não metas negativas → `test_perfil_fora_da_faixa` (Task 4).
5. Requisição com cookie de outro deploy (segredo trocado) → 401 limpo, não 500 → `test_cookie_invalido` (Task 3).

---

### Task 1: Esqueleto do repo e CI de testes

**Files:** Create `pyproject.toml`, `Makefile`, `.gitignore`, `.env.example`, `README.md` (stub), `src/hachibu/{__init__,config,app}.py`, `tests/test_health.py`, `.github/workflows/ci.yml`.

**Interfaces — Produces:** `Settings` (pydantic-settings ou dataclass de env: `DB_PATH`, `SESSION_SECRET`, `INVITE_CODE`, `APP_TZ="America/Sao_Paulo"`, `COOKIE_SECURE=true`); `create_app(settings: Settings) -> FastAPI`; `from_env() -> FastAPI` (factory do uvicorn).

- [ ] `git init`, branch `main`. **Confirmar com o Diego antes** de `gh repo create dpontejs/hachibu --public --source . --push`.
- [ ] Teste `test_healthz`: `GET /healthz` → 200 `{"ok": true}`. Rodar e ver falhar.
- [ ] Implementar `create_app` com `/healthz`; pyproject no padrão do `today` (ruff line 110, select E,F,I,UP,B,SIM).
- [ ] Makefile: `install`, `test` (`uv run pytest` + `npm --prefix web test -- --run` quando `web/` existir), `lint`, `dev` (uvicorn --reload + `vite`). CI: job `test` = `uv sync --frozen`, ruff check/format, pytest.
- [ ] `make test` verde → commit `chore: esqueleto do projeto com healthz e CI`.

### Task 2: Banco e migrações

**Files:** Create `src/hachibu/db.py`, `src/hachibu/migrations/001_inicial.sql`, `tests/conftest.py`, `tests/test_db.py`.

**Interfaces — Produces:** `connect(path: str) -> sqlite3.Connection` (WAL, `foreign_keys=ON`, `row_factory=Row`); `migrate(conn) -> None` (aplica `NNN_*.sql` em ordem, registra em `schema_version`); fixture `client` (app com `tmp_path` e `COOKIE_SECURE=false`) e `make_user(email) -> TestClient logado`.

Tabelas de 001: `users(id, email UNIQUE, senha_hash, criado_em)`, `profiles(user_id PK FK, sexo, idade, altura_cm, peso_kg, objetivo, nivel, dias_semana, minutos_sessao, equipamento, percentual_gordura NULL, cintura_cm NULL, condicoes_saude NULL)`, `goals(user_id PK FK, kcal, proteina_g, carbo_g, gordura_g, agua_ml)`, `meals(id, user_id FK, data TEXT, criado_em, nome, kcal, proteina_g, carbo_g, gordura_g, fonte)`, `water_logs(id, user_id FK, data TEXT, criado_em, ml)`; índices `(user_id, data)`.

- [ ] Testes `test_migrate_cria_tabelas` e `test_migrate_idempotente` (rodar 2×, sem erro, versão 1). Falhar → implementar → passar → commit `feat: banco sqlite com migracoes`.

### Task 3: Cadastro com convite, login e sessão

**Files:** Create `src/hachibu/auth.py`, `tests/test_auth.py`.

**Interfaces — Produces:** rotas `POST /api/auth/signup {email, senha, convite}` → 201 + cookie `hachibu_session`; `POST /api/auth/login {email, senha}` → 200 + cookie; `POST /api/auth/logout` → 204; `GET /api/me` → `{email, perfil_completo: bool}`; dependência `current_user(request) -> int` (401 sem sessão válida). Cookie: assinado (`TimestampSigner`), httponly, samesite=lax, secure conforme config, 90 dias. Senha: argon2, mínimo 8 caracteres.

- [ ] Testes: `test_signup_com_convite_valido`; `test_signup_convite_errado` → 403; `test_signup_email_repetido` → 409; `test_email_normalizado`; `test_senha_curta` → 422; `test_login_senha_errada` → 401; `test_login_rate_limit` (6ª falha do mesmo IP em 10 min → 429; reaproveitar a ideia do `LoginLimiter` do `today`); `test_cookie_invalido` → 401; `test_logout_encerra_sessao`.
- [ ] Falhar → implementar → passar → commit `feat: cadastro com convite e login por sessao`.

### Task 4: Perfil e metas por fórmula

**Files:** Create `src/hachibu/metas.py`, `src/hachibu/perfil.py`, `tests/test_metas.py`, `tests/test_perfil.py`.

**Interfaces — Produces:** `PerfilIn` (sexo `"M"|"F"`; idade 14–90; altura_cm 120–230; peso_kg 30–250; objetivo `"perder"|"manter"|"ganhar"`; nivel `"iniciante"|"intermediario"|"avancado"`; dias_semana 1–7; minutos_sessao 15–180; equipamento `"academia"|"casa_halteres"|"peso_corporal"`; **opcionais**: percentual_gordura 3–60, cintura_cm 40–200, condicoes_saude texto ≤ 500 caracteres, ex.: "hipertensão, dor no joelho esquerdo"; esse texto é dado sensível, nunca vai para logs e na etapa 2 alimenta a entrevista e os guardrails do coach); `Metas(kcal, proteina_g, carbo_g, gordura_g, agua_ml: int)`; `calcular_metas(p: PerfilIn) -> Metas` (pura, sem LLM); `PUT /api/perfil` → 200 `{perfil, metas}` (grava ambos); `GET /api/perfil` → 200 ou 404.

Fórmula (fixa): BMR Mifflin-St Jeor `10·peso + 6,25·altura − 5·idade + (5 se M, −161 se F)`; **se `percentual_gordura` for informado, usa Katch-McArdle** `370 + 21,6·massa_magra`, com `massa_magra = peso·(1 − %/100)`, mais precisa para quem sabe a composição corporal; fator por dias: ≤2 → 1,375; 3–4 → 1,55; ≥5 → 1,725; objetivo: perder ×0,80, manter ×1,00, ganhar ×1,10; piso de kcal 1500 (M) / 1200 (F); proteína g/kg: perder 2,2, manter 1,8, ganhar 2,0; gordura 0,8 g/kg; carbo = (kcal − 4·prot − 9·gord)/4, mínimo 0; água 35 ml/kg. Arredondar só no fim (`round`).

- [ ] Testes: `test_metas_homem_manter` (M, 30, 180, 80, 4 dias, manter → kcal 2759, prot 144, gord 64, carbo 402, água 2800); `test_metas_piso_feminino` (F, 50, 150, 45, 1 dia, perder → kcal 1200); `test_metas_com_percentual_gordura` (o mesmo homem com 15% → Katch-McArdle: kcal 2850, prot 144, gord 64, carbo 425); `test_perfil_sem_opcionais_aceito`; `test_perfil_fora_da_faixa` → 422; `test_put_perfil_grava_metas`; `test_me_perfil_completo_vira_true`.
- [ ] Falhar → implementar → passar → commit `feat: perfil e metas por formula`.

### Task 5: Hoje, refeição manual e água

**Files:** Create `src/hachibu/diario.py`, `tests/test_diario.py`.

**Interfaces — Produces:** `POST /api/refeicoes {nome, kcal 0–5000, proteina_g, carbo_g, gordura_g ≥0}` → 201 (fonte `"manual"`); `POST /api/agua {ml 1–2000}` → 201; `GET /api/hoje` → `{data: "AAAA-MM-DD", metas: Metas, consumido: {kcal, proteina_g, carbo_g, gordura_g}, agua_ml, refeicoes: [{id, nome, kcal, criado_em}]}`; `hoje(tz: str, agora: datetime | None = None) -> date` (injetável nos testes).

- [ ] Testes: `test_saldo_do_dia` (2 refeições + 2 águas somam certo); `test_hoje_usa_fuso_de_sao_paulo` (registro às 02:30 UTC conta no dia anterior); `test_hoje_sem_perfil` → 409 `{"detail": "perfil_incompleto"}`; `test_usuario_nao_ve_diario_de_outro` (B registra; `GET /api/hoje` de A não mostra nada de B); `test_rotas_exigem_login` (401 sem cookie em todas as `/api/*` exceto auth e healthz).
- [ ] Falhar → implementar → passar → commit `feat: tela hoje com refeicao manual e agua`.

### Task 6: Front PWA no tema A

**Files:** Create `web/` (Vite React TS): `index.html` (meta `apple-mobile-web-app-capable`, `theme-color #12141a`, `apple-touch-icon`), `public/manifest.webmanifest` (`display: standalone`, nome "Hachibu"), `public/icons/icon-{180,192,512}.png`, `public/fonts/*.woff2`, `src/{main.tsx, api.ts, theme.css}`, `src/layout/Shell.tsx`, `src/pages/{Entrar,Cadastro,Perfil,Hoje}.tsx`, `src/pages/Hoje.test.tsx`. Modify `src/hachibu/app.py` (montar `web/dist` + fallback SPA para rotas fora de `/api`).

**Interfaces — Consumes:** rotas das Tasks 3–5. `api.ts` expõe funções tipadas por rota; 401 → redireciona para `/entrar`; 409 `perfil_incompleto` → `/perfil`.

Telas: Entrar, Cadastro (com campo convite), Perfil (formulário da etapa 1; ao salvar mostra as metas calculadas), Hoje (como o mockup A: data + streak placeholder, card kcal com barra segmentada, macros, água com 12 gotas e botões +250/+500 ml, lista de refeições e formulário "adicionar manual"). Comida/Treino/Progresso: rota com "em breve".

- [ ] Teste vitest `Hoje.test.tsx`: com `fetch` mockado (kcal 1640/2300), renderiza "1640" e "660 restantes", e 6 de 12 gotas preenchidas para 1500/3000 ml. Falhar → implementar → passar.
- [ ] `npm run typecheck && npm run build`; `make dev`; conferir no navegador em 390 px e 1440 px (navegação inferior × barra lateral + painel do coach). Salvar prints em `docs/prints/estrutura-inicial-{celular,desktop}.png`.
- [ ] Commit `feat: pwa no tema sutil com telas de entrada, perfil e hoje`.

### Task 7: Imagem Docker e publicação no GHCR

**Files:** Create `Dockerfile` (estágio `node:22-slim` builda `web/`, estágio uv como no `today`, runtime `python:3.12-slim` com usuário 10001, `/data` volume, HEALTHCHECK em `/healthz`, `uvicorn hachibu.app:from_env --factory --proxy-headers`), `.dockerignore`, `compose.yml` (dev local). Modify `.github/workflows/ci.yml` (job `image`: build, smoke, push `:sha-*` e `:main` só na main, como no `today`).

- [ ] Smoke no CI: container `--read-only --tmpfs /tmp --cap-drop ALL` fica healthy; `curl /` contém `<div id="root">`; `curl /manifest.webmanifest` contém `"standalone"`; `curl /api/me` → 401.
- [ ] `docker build` + o mesmo smoke local verdes → commit `chore: imagem docker e publicacao no ghcr`.

### Task 8: Stack no infra (PR no repo `~/infra`, branch `feat/hachibu`)

**Files (infra):** Create `stacks/hachibu/compose.yml` (cópia do `today`: imagem `ghcr.io/dpontejs/hachibu:main`, volume `hachibu_data:/data`, read-only, `cap_drop: ALL`, rede `web`), `ansible/roles/stacks/templates/hachibu.env.j2` (`SESSION_SECRET`, `INVITE_CODE`). Modify `stacks/caddy/conf/Caddyfile` (bloco `hachibu.{$DOMAIN}` → `hachibu:8000`, `import security_headers`), `ansible/roles/stacks/tasks/main.yml` (assert + template, como o `today`), `handlers/main.yml` (`Restart hachibu`), `ansible/group_vars/all.yml` (`stacks_enabled` e `auto_update_stacks`), `terraform/variables.tf` (subdomínio `hachibu`).

- [ ] `make test` e `make lint` do infra verdes → commit `feat: stack do hachibu` → PR.
- [ ] Diego: `HACHIBU_SESSION_SECRET` e `HACHIBU_INVITE_CODE` em `~/.config/infra/secrets.env`, `terraform apply`, `make configure`.
- [ ] Verificação ponta a ponta: `curl -fsS https://hachibu.diegoponte.dev/healthz`; no iPhone, Safari → Adicionar à Tela de Início → abre sem barra do navegador → cadastro com convite → perfil → Hoje mostra as metas → +500 ml de água atualiza. No computador, o mesmo fluxo em layout de 3 colunas.
