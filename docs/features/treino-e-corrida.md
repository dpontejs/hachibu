# Treino e corrida

- **Data:** 2026-11-28
- **Status:** aprovada
- **ADRs:** —

## Objetivo

A aba TREINO passa a ter o plano da semana (musculação e corrida juntas) e o registro do que foi feito. O Hachibu monta um **plano base em código** a partir do perfil. Depois o aluno o ajusta conversando com o coach: troca exercícios, muda a divisão, sobe o nível. Toda mudança é validada em código e só vale depois de aprovada. O primeiro usuário é iniciante na corrida e está sem preparo, então a corrida começa alternando corrida e caminhada.

**Princípio:** tudo é personalizável. O plano base nasce das preferências declaradas, e não de um único padrão. O que o formulário não cobre, o coach ajusta pela conversa. O diferencial do Hachibu é esse: um plano que é seu, mais um coach para ajudar a mudá-lo com segurança.

## Fora de escopo

- Carga-alvo e progressão automática de carga: a carga é digitada pelo aluno, e o app mostra a última usada.
- Ritmos por fórmula do 5 km: ficam para quando houver o primeiro 5 km. Também não há GPS, relógio, Strava ou Hevy.
- Aprovação parcial de uma proposta: aqui é tudo ou nada, com recusa com motivo.
- Cronômetro de intervalos com som ou vibração, e a tela Progresso (gráficos de carga e ritmo).

## Decisões

- **Catálogo de exercícios em código** (`exercicios.py`), com cerca de 70 itens: `id` (slug), nome, grupo muscular, padrão de movimento e equipamentos (`academia`, `casa_halteres`, `peso_corporal`). O aluno pode criar exercícios próprios (tabela `exercicios_proprios`). O plano e o histórico apontam para um id, para que a "última carga" não se parta entre nomes diferentes.
- **Plano base sem LLM** (`plano_base(perfil) -> PlanoIn`):
  - A divisão vem de `dias_semana`: 2 ou 3 dias dão corpo inteiro A/B; 4 ou mais dão superior/inferior, com até 4 dias de musculação.
  - As séries e repetições vêm do `nivel`, e a duração de `minutos_sessao`.
  - Os exercícios vêm do catálogo, filtrados pelo `equipamento`.
  - A corrida para `iniciante` usa a tabela de progressão de corrida e caminhada (`PROGRESSAO_INICIANTE`): 9 semanas, 3 sessões por semana, de "1 min correndo / 2 min andando × 7" até "25 min contínuos", com o tempo correndo subindo no máximo 50% por semana, sempre com 5 min de caminhada de aquecimento.
  - Para intermediário ou avançado, a corrida é 2 a 3 sessões leves por tempo, com uma mais longa.
  - As corridas vão nos dias sem perna pesada. Há pelo menos 1 dia de descanso total.
- **Nível de corrida separado** *(decisão do builder)*: campo opcional novo no perfil, `nivel_corrida: iniciante | intermediario | avancado`. Se ficar vazio, vale `iniciante`. Dá para ser intermediário na musculação e iniciante na corrida.
- **Preferências de cardio no perfil** (opcionais, todas com padrão):
  - `dias_semana` passa a significar os dias em que o aluno **pode** treinar.
  - `corrida_quando: automatico | mesmo_dia | dias_separados`, com padrão `automatico`:
    - `automatico`: com 5 dias ou mais, a corrida vai para dias separados; com menos, fica no mesmo dia da musculação.
    - `mesmo_dia`: a corrida fica sempre depois da musculação.
    - `dias_separados`: corrida e musculação nunca no mesmo dia, dentro do limite de dias.
  - `corridas_semana`: 1 a 7, sem valor = 3. Com `mesmo_dia`, "cardio todo treino" é `corridas_semana = dias_semana`.
  - Quando a corrida fica no mesmo dia, `minutos_sessao` vale para a soma das duas. O plano base encurta a musculação (menos séries de acessórios) para caber.
- **Perna pesada** *(decisão do builder)*: um dia com 6 ou mais séries de quadríceps, posterior, glúteos ou panturrilha. É o mesmo limiar para alocar as corridas e para a regra 4. Corrida e caminhada ou corrida leve podem ficar no mesmo dia da musculação, ou no dia seguinte a perna. Só o intervalado e o longão evitam o dia seguinte a perna.
- **O plano base ignora as condições físicas**, porque são texto livre. A tela mostra "você tem condições registradas: peça ao coach para adaptar".
- **Versões:** cada plano aprovado vira uma versão nova. A anterior fica, porque o histórico aponta para ela.
- **Avanço da corrida iniciante** *(decisão do builder)*:
  - Os dias de corrida do plano marcados `progressao=true` mostram o treino da semana atual da tabela, que fica em `progressao_corrida.semana`. O `GET /plano` monta esses dias na hora.
  - O avanço **não cria versão nova** e não passa pela regra 5, porque a tabela já foi desenhada para progredir com segurança.
  - A conta é por sessões desde o último avanço, não pela semana do calendário. Qualquer corrida registrada conta, pela tela ou pelo coach.
  - A cada 3 corridas, se 2 ou mais tiverem esforço 9 ou 10, a semana se repete e a contagem recomeça. Senão, avança.
  - Depois da semana 9, a progressão termina: os dias viram "leve 30 min" fixos, e a tela sugere pedir ao coach o próximo passo.
  - Se o coach substituir uma corrida da progressão por uma corrida fixa, aquele dia sai da progressão (`progressao=false`).
- **Perfil mudou e o plano ficou inválido** *(decisão do builder)*: a aba TREINO roda o validador contra o perfil atual e mostra o aviso "seu perfil mudou", com duas saídas: "gerar novo plano base" (`POST /plano/base?substituir=true`, que cria versão nova com origem base) ou pedir ao coach.
- **O coach altera o plano propondo a semana inteira**: `propor_plano(plano: PlanoIn, justificativa)`. O código valida, calcula a diferença item a item para a versão atual e pausa com `interrupt()`. O card mostra só as mudanças. Ao aprovar, grava a versão nova com `origem="coach"`.

## Regras do validador (`validar_plano(plano, perfil, anterior) -> list[str]`)

1. Todo exercício existe no catálogo ou nos exercícios próprios, e cabe no `equipamento` do perfil.
2. Há pelo menos 1 dia de descanso total. O número de dias com treino é no máximo `dias_semana`.
3. A duração estimada do dia, `Σ séries × (40 s + descanso)` mais a corrida (inclusive em dia só de corrida), é no máximo `minutos_sessao` × 1,15.
4. Não há intervalado nem longão no dia seguinte a um dia com 6 ou mais séries de pernas.
5. O volume de corrida da semana (minutos) é no máximo 1,10 × o da versão anterior. A primeira versão é livre.
6. O longão tem no máximo 40% do volume semanal de corrida. Com 3 corridas de 30 min, um teto de 30% deixaria o longão menor que a leve, por isso vale 40%.
7. Séries por grupo muscular na semana: no máximo 25. Séries e repetições dentro de faixas sãs (1–10 séries, 1–30 repetições).
8. Intervalado e longão nunca em dias seguidos.
9. O mesmo exercício não aparece duas vezes no mesmo dia.

O plano base nunca grava um plano que reprove nessas regras (`POST /plano/base` valida antes, nas semanas 1 e 9). O que ele não pôde seguir das preferências (corridas a menos para sobrar musculação, corrida em dias separados por falta de tempo, corrida fora por falta de tempo) vira **nota** gravada com a versão e mostrada na tela.

## Contratos

```python
class ExercicioPlano(BaseModel): exercicio_id: str; series: int; reps_min: int; reps_max: int; descanso_s: int = 90
class CorridaPlano(BaseModel):
    progressao: bool = False                            # True: o treino vem da semana atual da tabela
    tipo: Literal["corrida_caminhada", "leve", "intervalado", "longao"]
    duracao_min: int
    corre_min: float | None = None; anda_min: float | None = None; repeticoes: int | None = None
    esforco_alvo: str  # ex. "3-4"
class DiaPlano(BaseModel):
    dia: int                                            # 0 = segunda
    nome: str                                           # "Superior A", "Descanso"
    exercicios: list[ExercicioPlano] = []
    corrida: CorridaPlano | None = None
class PlanoIn(BaseModel): dias: list[DiaPlano]          # 7 dias, extra=forbid

GET  /api/plano                 → {versao, origem, criado_em, dias, semana_corrida}  | 404 sem plano
POST /api/plano/base            → 201 (gera a partir do perfil; 409 se já existe plano, salvo ?substituir=true)
GET  /api/exercicios?q=         → catálogo + próprios         POST /api/exercicios → 201 (próprio)
POST /api/sessoes               → 201 {tipo: musculacao|corrida, data, plano_dia, local?}
PUT  /api/sessoes/{id}          → séries [{exercicio_id, ordem, carga_kg?, reps}] | corrida {duracao_min, distancia_km?, esforco}
GET  /api/sessoes?de=&ate=      → histórico         GET /api/locais → locais já usados
GET  /api/exercicios/{id}/ultima?local= → séries da última sessão (do mesmo local; se não houver, de qualquer local)
```

- **Perfil:** colunas `nivel_corrida`, `corrida_quando` e `corridas_semana` em `profiles` (todas opcionais), e os campos num grupo "CORRIDA" do formulário.
- **Banco:** migração `006_treino.sql` com as tabelas `exercicios_proprios`, `planos` (versão, origem, ativo), `plano_dias`, `plano_exercicios`, `plano_corridas`, `progressao_corrida` (semana atual), `sessoes`, `series` e `corridas`. Toda tabela tem `user_id`.
- **Tools do coach:**
  - `ler_plano()`, `historico_exercicio(exercicio_id, local?)` e `historico_corrida()`;
  - `registrar_corrida(duracao_min, esforco, distancia_km?)`, que segue a mesma regra de avanço;
  - `propor_plano(plano, justificativa)`, com `interrupt()`.

## PRs

1. **Plano base e tela da semana:** catálogo, `plano_base`, validador, versões, `GET/POST /plano` e a aba TREINO com a semana e o dia de hoje (só leitura).
2. **Registro:** sessões no estilo Hevy (carga e repetições por série, já preenchidas com a última vez, e local opcional com sugestões), registro de corrida e avanço da progressão.
3. **Coach:** as tools, `propor_plano` com o card de diferenças, e a skill de corrida atualizada para iniciante.

## Critérios de aceite (como testes)

- [ ] `test_plano_base_iniciante_3_dias`: dado iniciante, 3 dias, 60 min, academia e `corrida_quando` automático, o plano tem corpo inteiro A/B com a corrida e caminhada da semana 1 no mesmo dia, 3 corridas, 4 dias de descanso, e passa no validador.
- [ ] `test_plano_base_cardio_todo_treino`: com `mesmo_dia`, 4 dias e `corridas_semana=4`, há corrida nos 4 dias de musculação.
- [ ] `test_plano_base_dias_separados`: com `dias_separados` e 6 dias, nenhum dia tem musculação e corrida juntas.
- [ ] `test_plano_base_respeita_equipamento`: com `peso_corporal`, nenhum exercício exige academia ou halteres.
- [ ] `test_validador_*`: uma regra por teste (intervalado depois de perna, +15% de corrida, sem descanso, duração estourada, exercício inexistente).
- [ ] `test_ultima_carga_prefere_o_mesmo_local`: dados um supino de 30 kg no local A e um de 24 kg no local B (mais recente), quando se pede a última do local A, então a resposta é 30 kg. Sem local, a resposta é 24 kg.
- [ ] `test_progressao_avanca_e_repete`: 3 corridas com esforço ≤ 8 avançam a semana; esforço 9 em 2 delas repete a semana.
- [ ] `test_propor_plano_invalido_nao_pausa` e `test_propor_plano_aprovado_vira_versao_nova` (diferença no card, origem coach).
- [ ] `test_plano_e_sessoes_de_outro_usuario_404`.
- [ ] Gemini real: "não gosto de leg press, troca" → a proposta muda só esse item. "Sou avançado, monta um treino mais pesado" → a proposta passa no validador.

## Verificação ponta a ponta

`make test`. Depois, em produção: gerar o plano, registrar um treino de musculação com local, registrar uma corrida e pedir ao coach uma troca de exercício.

## Riscos e dúvidas abertas

- Uma tabela de progressão própria, inspirada em programas públicos de corrida e caminhada, sem copiar nenhum programa com marca.
- A estimativa de duração é grosseira, e por isso a tolerância é de 15%.
