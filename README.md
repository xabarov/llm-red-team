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
- `tasks/active/` — небольшой список текущих задач.
- `tasks/archive/` — история завершённых задач, исключённая из обычного контекста.
- `.codex/project-memory.md` — короткая оперативная память проекта.

Описание задачи: [`docs/brief.md`](docs/brief.md). Архитектура:
[`docs/architecture.md`](docs/architecture.md). Стратегия:
[`docs/strategy.md`](docs/strategy.md). Этапы работы:
[`docs/roadmap.md`](docs/roadmap.md). Инструкции стенда:
[`infra/README.md`](infra/README.md). Русские материалы по статьям:
[`research/papers/ru/README.md`](research/papers/ru/README.md).

## Правило контекста

В начале сессии не нужно читать весь репозиторий. Достаточно `AGENTS.md`, памяти
проекта и активных задач. Подробности открываются по ссылкам только для текущей
работы. После завершения задача переносится из `tasks/active/` в ежемесячный
архив, а оперативная память сокращается до актуальных решений и следующего шага.
