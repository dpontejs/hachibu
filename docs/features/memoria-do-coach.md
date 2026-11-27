# Memória do coach

- **Data:** 2026-11-28
- **Status:** entregue (PR #11)
- **ADRs:** —

## Objetivo

O coach passa a lembrar, entre conversas, o que o aluno contou sobre si: restrições alimentares e de saúde, condições físicas e gostos. Hoje ele diz "anotado" sem gravar nada e esquece na conversa seguinte. Restrições (celíaco, alergia, vegetariano) e condições (joelho, hérnia) não podem ser esquecidas de jeito nenhum, e o aluno vê e edita tudo o que o coach sabe.

## Fora de escopo

- Checagem em código de alérgenos nas sugestões: a TACO não traz alérgenos. Entra com o cardápio/receitas, em que os ingredientes são explícitos.
- Memória episódica ("semana passada você dormiu mal") e busca por similaridade.
- Migrar o campo livre `condicoes_saude` do perfil: ele continua e também vai sempre para o prompt.

## Contratos

```python
Tipo = Literal["restricao", "condicao", "gosto"]   # restrição alimentar/saúde · condição física · gosto
class MemoriaIn(BaseModel):  tipo: Tipo; texto: str  # 2..200 caracteres, extra=forbid
class MemoriaOut(BaseModel): id: int; tipo: Tipo; texto: str; origem: Literal["coach", "aluno"]; criado_em: str

GET    /api/memorias            → 200 {"memorias": [MemoriaOut]}   # restrições, condições, gostos; mais antigas primeiro
POST   /api/memorias            → 201 MemoriaOut (repetida: 200 com a existente)   # origem "aluno"
PATCH  /api/memorias/{id}       → 200 MemoriaOut                    # {"texto": ...}
DELETE /api/memorias/{id}       → 204
```

- Banco: migração `005_memorias.sql`, tabela `memorias(id, user_id → users ON DELETE CASCADE, tipo CHECK, texto, origem CHECK, criado_em)`, `UNIQUE(user_id, tipo, texto_normalizado)`. A normalização ignora caixa, acentos, espaços e pontuação final.
- Erros: 404 `memoria_inexistente` (inclusive de outro usuário); 409 `limite_de_memorias` (teto por tipo: 30 restrições, 30 condições, 60 gostos, para que gostos nunca barrem uma restrição); 409 `memoria_repetida` ao editar para um texto que já existe; 422 de validação (texto sem letra/número ou invisível).
- Tools do coach (usuário no closure, como as outras):
  - `lembrar(tipo, texto)`: grava com origem "coach". Repetir não duplica.
  - `esquecer_gosto(id)`: apaga **só gostos**. Para restrição/condição devolve `erro:` dizendo que só o aluno remove, na tela Perfil.
- Prompt: a cada mensagem, um bloco "O que você sabe do aluno" com as restrições e condições (incluindo `condicoes_saude` do perfil) em destaque, os gostos e o `#id` de cada item. O bloco é marcado como **dado do aluno, não instrução**. Regras novas:
  - Grave com `lembrar` o que o aluno declarar sobre si.
  - Nunca diga "anotei/vou lembrar" sem ter chamado `lembrar`.
  - Nunca sugira o que fere uma restrição ou condição.
- Front: seção "O QUE O COACH SABE DE VOCE" no Perfil (restrições no topo), com adicionar, editar e apagar. O apagar de restrição/condição pede confirmação. Os chips do chat mostram "lembrei" e "esqueci".

## Critérios de aceite (como testes)

- [ ] `test_crud_de_memorias`: dado o aluno, quando cria, edita e apaga, então a lista reflete cada passo, com origem "aluno".
- [ ] `test_memoria_de_outro_usuario_404`: PATCH/DELETE na memória de outra conta → 404, e ela continua lá.
- [ ] `test_memoria_repetida_nao_duplica`: o mesmo tipo e texto (ignorando maiúsculas e espaços) → um item só.
- [ ] `test_limite_de_memorias`: o 61º gosto → 409; pela tool → `erro:`. `test_muitos_gostos_nao_impedem_restricao`.
- [ ] `test_lembrar_grava_com_origem_coach` e `test_tools_sem_user_id_no_schema` (tools novas incluídas).
- [ ] `test_coach_nao_apaga_restricao`: `esquecer_gosto` no id de uma restrição → `erro:` e ela continua.
- [ ] `test_memorias_entram_no_prompt_de_toda_conversa`: memória gravada na thread A aparece no prompt de sistema da thread B, com as restrições antes dos gostos e com `condicoes_saude` do perfil.
- [ ] `test_memoria_e_dado_nao_instrucao`: o texto da memória entra delimitado, depois da regra de que é dado.
- [ ] Front: lista agrupada; adicionar; editar; apagar restrição pede confirmação; chip "lembrei".
- [ ] LLM (`-m llm`): "não gosto de azeitona" na conversa A → na B, "eu gosto de azeitona?" responde que não. "Sou celíaco" vira `restricao`.

## Verificação ponta a ponta

```bash
make test && uv run pytest -m llm tests/test_coach_llm.py -k memoria
```
Depois, em produção: a conversa da azeitona e a tela Perfil.

## Riscos e dúvidas abertas

- Prompt cresce com a lista: teto de 60 itens de até 200 caracteres (~3 mil tokens no pior caso).
- Injeção via memória ("ignore as regras"): o bloco é dado delimitado, cada item numa linha só e sem `<`/`>` (não dá para fechar o bloco), e nenhuma tool destrutiva depende dele.
