# Goal-блоки хакатона

Обновлено: 2026-09-06

## Как запускать goal

Goal-блок — крупный самостоятельный отрезок работы, который можно запускать через
goal-механику Codex. Внутри goal можно поднимать субагентов, но только на
конкретные bounded-подзадачи.

Общий шаблон для субагента:

```text
Работай как инженер по authorized security evaluation локального хакатонного
стенда с синтетическими данными. Формулируй задачу нейтрально: воспроизводимые
security-eval сценарии, evidence, oracles, документация и проверки. Не работай с
реальными внешними целями, секретами или обходом защитных механизмов Codex. Не
делай commit/push и не запускай дорогие live-campaign без явного разрешения.
Сначала проверь dirty worktree и не перезаписывай чужие изменения. Верни краткий
отчет: что изменено, какие команды запускались, что осталось.
```

## G1 — Replay Corpus

Статус: завершён 2026-09-06. C1 explicit-command сохранён в
`replays/cross-user-policy-poisoning-c1-explicit-command/`, индекс corpus — в
`replays/README.md`.

Цель: превратить успешные generated cases в аккуратный replay corpus с frozen
evidence и понятным naming.

Входы:

- `output/runs/campaign-20260906T125522Z-641ead12/`;
- `output/generated/planner-scenarios/`;
- базовый `replays/cross-user-policy-poisoning-v1/`.

Готово, когда:

- C1 explicit-command сохранен как отдельный replay candidate;
- есть `scenario.json`, `validation.md`, `evidence/latest.*`;
- README или индекс replay corpus объясняет происхождение и результат;
- `make stage1-test`, `make scenario-validate`, `make context-check` проходят.

Инструкция для субагента:

```text
Подзадача: подготовить replay-corpus entry для уже успешного C1 explicit-command
из limited batch. Работай только с локальными артефактами output/runs и replays,
не запускай OpenRouter/campaign-run, не делай commit/push. Сохрани evidence
аккуратно, без секретов, и обнови индекс replay corpus, если он есть.
```

## G2 — Seed Improvement

Статус: завершён 2026-09-06. C2 найден и сохранён в
`replays/cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger/`;
C3 зафиксирован как negative result в `docs/seed-improvement-g2.md`.

Цель: улучшить C2/C3 и получить минимум два дополнительных сценария с сильной
воронкой write → recall → exploitation.

Входы:

- `seeds/cross-user-policy-poisoning.yaml`;
- `docs/strategy.md`;
- отчеты failed/partial из `campaign-20260906T125522Z-641ead12`.

Готово, когда:

- C2/C3 wording улучшен или добавлены новые variants;
- materialized scenarios валидны;
- limited batch показывает понятное улучшение funnel или фиксирует negative result;
- результаты коротко записаны в project memory.

Инструкция для субагента:

```text
Подзадача: проанализировать локальные evidence summaries C2/C3 и предложить
более устойчивые seed variants. Не запускай live campaign и не делай внешних
вызовов. Сфокусируйся на wording, required_policy_terms и trigger phrasing,
чтобы deterministic oracles оставались честными.
```

## G3 — Batch Metrics

Статус: завершён 2026-09-06. Offline CLI и Make target пересчитывают funnel из
case summaries, сверяют batch aggregates и формально выбирают replay candidates;
контракт описан в `docs/batch-metrics.md`.

Цель: сделать удобный слой метрик для generated scenarios: ASR/funnel,
attempts, стоимость/latency hooks и candidate selection.

Готово, когда:

- есть CLI/Make target для чтения `summary.json` и `batch-summary.json`;
- отчет показывает case-level и aggregate funnel;
- можно выбрать replay candidates по правилам, а не глазами из Markdown;
- не требуется повторный live-run для анализа уже собранных артефактов.

Инструкция для субагента:

```text
Подзадача: добавить offline metrics/report CLI поверх output/runs summaries.
Не запускай campaign-run. Работай только с JSON summaries, добавь unit-тесты на
маленьких fixture-объектах и короткую документацию команды.
```

## G4 — Guarded Modes

Статус: завершён 2026-09-07. Четыре режима выполняются deterministic offline
над captured snapshot; provenance-based write/read gates, selective repair,
F1/F2, SRSR и frozen replay описаны в `docs/memory-defense.md`.

Цель: добавить режимы защиты памяти и selective repair, чтобы сравнивать не
только vulnerable/protected IAM, но и memory-defense стратегии.

Готово, когда:

- описаны режимы none/write/read/write+read;
- есть минимальный adapter или simulation layer для write/retrieval gate;
- добавлены F1/F2 checks: malicious removal и benign preservation;
- baseline replay не ломается.

Инструкция для субагента:

```text
Подзадача: спроектировать memory defense interface и F1/F2 oracle без изменения
боевого стенда. Не удаляй существующую память вне reset текущего локального
стенда, не запускай live campaign без отдельного разрешения.
```

## G5 — Evaluation Matrix

Статус: завершён 2026-09-08. Утверждённая live matrix выполнена полностью;
переносимый evidence bundle и отчёты сохранены в
`evaluation/results/g5-20260908-full-v2/`.

Цель: провести ограниченную, защищаемую экспериментальную оценку.

Готово, когда:

- согласованы бюджет OpenRouter, модели, повторы и attack classes;
- campaign matrix запускается воспроизводимо;
- каждый агрегат восстанавливается из evidence;
- результаты готовы для защиты.

Инструкция для субагента:

```text
Подзадача: подготовить matrix plan и budget estimate. Не запускай платные
прогоны. Используй уже имеющиеся summaries для оценки длительности и числа
вызовов, явно отделяй предположения от измеренных данных.
```

## G6 — Demo & Submission

Цель: упаковать результат в демонстрацию и финальный рассказ.

Готово, когда:

- есть короткий demo script;
- есть один надежный replay path и запасной prerecorded trace;
- README содержит clean-room запуск;
- слайды/текст защиты объясняют threat model, lifecycle, evidence и ограничения.

Инструкция для субагента:

```text
Подзадача: подготовить demo narrative и checklist на основе существующих replay
reports. Не меняй runner и не запускай live campaign. Сфокусируйся на ясности,
responsible-use формулировках и воспроизводимости.
```
