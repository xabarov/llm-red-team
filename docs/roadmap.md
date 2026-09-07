# Этапы работы над хакатоном

Обновлено: 2026-09-06

## Принцип прохождения

Этап начинается только после прохождения gate предыдущего этапа. Демонстрационный
replay-кейс поддерживается рабочим начиная с этапа 1; новые возможности не должны
ломать его воспроизводимость.

Крупные рабочие блоки для goal-механики Codex вынесены в
[`docs/goal-blocks.md`](goal-blocks.md). Каждый goal содержит bounded-scope,
gate и нейтральную инструкцию для субагентов под authorized локальный стенд.

```mermaid
flowchart LR
    S0[0. Основа] --> S1[1. Demo spine]
    S1 --> S2[2. Scenario engine]
    S2 --> S3[3. LLM intelligence]
    S3 --> S4[4. Defense & repair]
    S4 --> S5[5. Evaluation]
    S5 --> S6[6. Demo & submission]
```

## Этап 0 — Основа

Статус: завершён.

Результаты:

- нормализованное ТЗ, threat model и выбранная гибридная архитектура;
- закреплённый upstream-стенд с vulnerable/protected режимами;
- OpenRouter и локальный Ollama как взаимозаменяемые профили;
- разбор трёх публикаций и seed benchmark OWASP;
- правила памяти проекта, задач и архива.

Gate: стенд поднимается одной командой, readiness и полный agent smoke проходят.

## Этап 1 — Вертикальный срез атаки

Статус: завершён.

Цель: доказать один сценарий целиком до внешнего последствия без универсального
движка.

Результаты:

- target adapter: reset, actor/session, vulnerable/protected, finalize;
- ручной сценарий cross-user policy-memory poisoning;
- нормализованные события запроса, memory write/read, inferred tool attempt и side effect;
- JSONL evidence bundle с SHA-256 manifest и редактированием секретов;
- программные W1/W2/E1/E2/E3 oracles и минимальный Markdown-отчёт;
- frozen replay `replays/cross-user-policy-poisoning-v1/`.

Gate: один и тот же replay демонстрирует последствие в vulnerable и блокировку
на IAM-границе в protected; каждое утверждение отчёта связано с evidence ID.

Последний успешный прогон: `stage1-20260905T113516Z-41f40693`,
evidence SHA-256 `bcb63adb1096a4140b78ae2da040ceb37a513df113a26787cbd2c44a86fdc9bd`.

## Этап 2 — Детерминированный scenario engine

Статус: завершён.

Цель: превратить вертикальный срез в воспроизводимый campaign runner.

Результаты:

- JSON Schema и YAML DSL для setup/inject/persist/trigger/verify/cleanup;
- конечный автомат стадий, таймауты, ошибки и однозначные статусы;
- snapshot/namespace isolation и гарантированный cleanup;
- параметризация actors, carrier, auth mode, payload и seed;
- batch runner и агрегирование checkpoint funnel.

Gate: статический набор кейсов повторяется с одинаковыми входами и структурой
evidence; инфраструктурная ошибка не считается успешной защитой.

Последний успешный campaign gate: `campaign-20260905T222418Z-091ac12d`,
evidence SHA-256 `8e529ee282428107556072cae7bf069bef9fd339b463ed89da98a6a7ab3f4594`.

## Этап 3 — LLM intelligence

Статус: в работе.

Цель: расширить поиск атак, не отдавая LLM контроль над доказательствами.

Результаты:

- OpenRouter planner генерирует только schema-valid сценарии;
- mutator адаптирует payload в пределах allowlist и бюджета шагов;
- semantic judge оценивает W2/E1/E2 по evidence allowlist и строгой JSON-схеме;
- программные gates проверяют citations, зависимости и наличие E3;
- успешные находки автоматически замораживаются в replay corpus;
- журналируются model slug, provider, параметры, token usage, стоимость и latency.

Gate: ни один LLM-verdict не может заменить отсутствующий memory diff, recall или
внешний side effect; replay успешной находки работает без повторной генерации.

## Этап 4 — Защита и selective repair

Статус MVP G4: завершён 2026-09-07 как deterministic offline simulation над
captured snapshot. Реализованы provenance/authority write/read gates, четыре
режима, selective repair и F1/F2/SRSR replay. Live interposition, OWASP baseline,
temporal validity и расширенная benign/FPR matrix остаются экспериментальной
работой следующих этапов; offline результат не заявляется как снижение live ASR.

Цель: сравнить не только уязвимость, но и рабочие меры защиты.

Результаты:

- baseline OWASP Agent Memory Guard;
- write gate с provenance, authority, scope и temporal validity;
- retrieval gate: память считается данными, а не инструкциями;
- четыре режима: none, write-only, read-only, write+read;
- F1 repair и F2 benign preservation из одного post-Write snapshot;
- benign regression suite и false-positive/utility metrics.

Gate: защита уменьшает E2E-ASR, не достигая результата очисткой всей памяти и не
ломая согласованный порог полезности.

## Этап 5 — Экспериментальная оценка

Цель: получить защищаемые числа, а не единичную удачную демонстрацию.

Результаты:

- зафиксированная матрица model × mode × attack class × carrier × seed;
- каналы C1-C3 в обязательном scope, C4 — если target поддерживает skills;
- несколько повторов для стохастических стадий;
- MPSR, MESR, E2E-ASR, SRSR, stealth, FPR, utility, latency и cost;
- доверительные интервалы и breakdown по checkpoints;
- ручная калибровка выборки judge-verdicts.

Gate: каждый агрегат восстанавливается из case-level evidence; версии моделей,
промптов, стенда и сценариев закреплены.

## Этап 6 — Демо и сдача

Цель: упаковать результат в короткий воспроизводимый рассказ.

Результаты:

- live или prerecorded trace `inject → persist → trigger → side effect`;
- сравнение vulnerable/protected/guarded на одном replay bundle;
- checkpoint funnel и таблица attack/utility trade-off;
- архитектурная схема, threat model, ограничения и responsible-use заметка;
- clean-room инструкция запуска и резервный локальный demo-профиль.

Gate: новый участник запускает демо по README; основной сценарий имеет запасной
replay и не зависит от доступности внешнего LLM в момент защиты.

## Где используется OpenRouter

| Компонент | Backend | Причина |
|---|---|---|
| Атакуемый agent | OpenRouter по умолчанию | Реалистичные reasoning и tool-use для разработки и замеров |
| Planner/mutator | OpenRouter | Нужны качество, вариативность и structured output |
| Semantic judge | OpenRouter, отдельная закреплённая модель | Нужна семантическая оценка; verdict ограничен evidence/gates |
| Smoke и аварийное демо | Ollama `qwen3:1.7b` | Нет внешней зависимости и расходов |
| Executor, reset, IAM, oracles, metrics | Без LLM | Воспроизводимость и проверяемость |
| PDF extraction/OCR | Poppler/Tesseract | LLM не улучшает механическое извлечение текста |

OpenRouter не является единственной точкой отказа: все найденные атаки сохраняются
как статические replay-кейсы, а для защиты готовится локальный профиль.
