# LLM Red Team Hackathon

Репозиторий для разработки agentic red-team решения для банковского агента с
долговременной памятью. ТЗ нормализовано, локальный upstream-стенд развёрнут,
а исследовательская база и стратегия MVP зафиксированы в репозитории.

## Быстрый старт

```bash
make doctor
make context-check
make stand-up
make stand-smoke
make stand-agent-smoke
make stage1-test
make stage1-run
make batch-metrics
make guarded-validate
make guarded-eval
make evaluation-plan
make evaluation-report
make evaluation-review-prepare
make evaluation-combined-report
```

`stand-up` использует OpenRouter при наличии `OPENROUTER_API_KEY` в `.env`.
Для полностью локального запуска используйте `make stand-up-local`; для явного
выбора OpenRouter — `make stand-up-openrouter`.

Актуальное состояние находится в [`.codex/project-memory.md`](.codex/project-memory.md), текущая работа — в [`tasks/active/README.md`](tasks/active/README.md).

## Структура

- `tz/` — входные сообщения и исходное ТЗ; не редактировать при нормализации.
- `docs/` — краткое ТЗ, стратегия, архитектура и решения.
- `research/` — каталог публикаций, OCR/extraction и русские разборы.
- `infra/` — описание и файлы стенда.
- `src/llm_red_team/` — runner, target adapter, evidence и deterministic oracles.
- `replays/` — замороженные воспроизводимые кейсы с evidence/manifest/report.
- `tasks/active/` — небольшой список текущих задач.
- `tasks/archive/` — история завершённых задач, исключённая из обычного контекста.
- `.codex/project-memory.md` — короткая оперативная память проекта.

Описание задачи: [`docs/brief.md`](docs/brief.md). Архитектура:
[`docs/architecture.md`](docs/architecture.md). Стратегия:
[`docs/strategy.md`](docs/strategy.md). Этапы работы:
[`docs/roadmap.md`](docs/roadmap.md). Инструкции стенда:
[`infra/README.md`](infra/README.md). Русские материалы по статьям:
[`research/papers/ru/README.md`](research/papers/ru/README.md).

Офлайн-воронка по уже собранным campaign artifacts и формальный выбор replay
кандидатов: [`docs/batch-metrics.md`](docs/batch-metrics.md). Команда
`make batch-metrics` не обращается к стенду или LLM.

Четыре offline memory-defense режима, selective repair и F1/F2:
[`docs/memory-defense.md`](docs/memory-defense.md). Они исполняются над
синтетическим captured snapshot и также не требуют стенда или LLM.

Ограниченная G5 matrix, бюджетный approval gate и восстановление агрегатов из
evidence: [`docs/evaluation-matrix.md`](docs/evaluation-matrix.md).

## Правило контекста

В начале сессии не нужно читать весь репозиторий. Достаточно `AGENTS.md`, памяти
проекта и активных задач. Подробности открываются по ссылкам только для текущей
работы. После завершения задача переносится из `tasks/active/` в ежемесячный
архив, а оперативная память сокращается до актуальных решений и следующего шага.
