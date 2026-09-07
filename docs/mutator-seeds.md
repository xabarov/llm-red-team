# Seed families и mutator output

Обновлено: 2026-09-06

## Назначение

Seed family описывает семейство вариантов поверх уже валидного campaign scenario. Это
не executor и не oracle: файл только задаёт параметры, patches и provenance. После
материализации каждый вариант становится обычным schema-valid scenario и дальше
запускается тем же deterministic runner.

## Формат

Минимальный файл:

```yaml
schema_version: seed-family/v1
id: cross-user-policy-poisoning
base_scenario: replays/cross-user-policy-poisoning-v1/scenario.json
provenance:
  kind: seed_family
  generator: manual
  backend: deterministic
  model:
  prompt_id: manual-seed-family-v1
variants:
  - id: c2-policy-document
    category: C2
    scenario_id: cross-user-policy-poisoning-c2-policy-document
    parameters:
      marker: RTM-C2-${run_id}
    patches:
      - path: [steps, inject.policy, content]
        value: "..."
```

Поля:

- `base_scenario` указывает на существующий DSL-сценарий.
- `parameters` на уровне family задают общие переменные, variant-parameters их
  переопределяют.
- `patches[].path` может быть строкой с dotted path или массивом компонентов.
  Для `steps` компонент после `steps` трактуется как `id` шага. Если в id есть
  точки, используем массив: `[steps, inject.policy, content]`.
- `provenance` фиксирует источник генерации: `manual`, будущий `openrouter`,
  конкретную модель, prompt/template id и hash исходного planner output.

## Поток данных

1. Planner/mutator создаёт или обновляет seed family.
2. `llm_red_team.mutator.materialize_family()` применяет patches к base scenario.
3. Каждый получившийся scenario валидируется через `schemas/scenario.schema.json`.
4. Campaign runner выполняет только валидные frozen scenarios; LLM не участвует в
   executor/oracle.

Первый seed-файл: `seeds/cross-user-policy-poisoning.yaml`.

## Planner

```bash
make planner-draft
make planner-openrouter
```

`planner-draft` только сохраняет prompt в `output/planner/` и не делает сетевых
вызовов. `planner-openrouter` делает один OpenRouter-запрос, валидирует
полученный `seed-family/v1` и сохраняет JSON с provenance. В executor/oracle этот
LLM-output не попадает напрямую: сначала он материализуется и проходит обычную
schema validation.

После planner-вызова можно материализовать полученный файл:

```bash
PYTHONPATH=src uv run python scripts/generate-scenarios.py \
  --seed output/planner/cross-user-policy-poisoning.seed-family.json \
  --output-dir output/generated/planner-scenarios
```

## Локальная материализация

```bash
make scenario-generate
```

Команда пишет JSON-сценарии в `output/generated/scenarios/`. Каталог `output/`
игнорируется Git, поэтому это временные артефакты для проверки и последующего
выбора кандидатов в replay corpus.
