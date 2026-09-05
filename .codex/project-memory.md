# Память проекта

Обновлено: 2026-09-05

## Цель

Подготовить воспроизводимое решение для LLM red-team хакатона: понять ТЗ, собрать стенд, изучить указанные публикации, реализовать и проверить стратегию.

## Текущее состояние

- Git-репозиторий и базовая структура созданы.
- Нормализованное ТЗ находится в `docs/brief.md`; стратегия и архитектура — в `docs/strategy.md` и `docs/architecture.md`.
- Устройство памяти стенда и white-box выводы зафиксированы в `docs/stand-memory-model.md`; ключевой рычаг атаки — global `agent_policy_memories` без `user_id`.
- Upstream-стенд закреплён на commit `f56b68b6a552d8cac6bb5e053ec28f5565d7555d`, запущен в Docker и проходит readiness и полный agent smoke test.
- Живой стенд использует OpenRouter: research agent и finalize/summarization `openai/gpt-4.1-mini`; локальный Ollama `qwen3:1.7b` сохранён как offline smoke/fallback профиль.
- Этап 1 завершён: `replays/cross-user-policy-poisoning-v1/` содержит сценарий, frozen evidence и validation report. Успешный run `stage1-20260905T113516Z-41f40693`, evidence SHA-256 `bcb63adb1096a4140b78ae2da040ceb37a513df113a26787cbd2c44a86fdc9bd`.
- Этап 2 закрыт: `cross-user-policy-poisoning-v1` переведен на schema-valid DSL, добавлен deterministic campaign runner, batch summary и совместимость со stage1 replay.
- Campaign gate пройден на живом стенде: `campaign-20260905T222418Z-091ac12d`, evidence SHA-256 `8e529ee282428107556072cae7bf069bef9fd339b463ed89da98a6a7ab3f4594`, обе ветки vulnerable/protected PASS.
- Poppler и Tesseract с моделями `eng`/`rus` установлены; pipeline выбирает текстовый слой PDF и использует OCR только для сканов.
- Все три публикации прочитаны постранично и сверены визуально. Для каждой подготовлен отдельный русский разбор с картой страниц и применением к хакатону; машинные переводы удалены по решению команды.

## Решения

- Оперативная память остаётся короткой и содержит только действующие факты, решения, блокеры и ближайшие шаги.
- Подробные знания хранятся в `docs/` и `research/`; завершённые задачи — в `tasks/archive/`.
- Исходные публикации не попадают в Git по умолчанию; их происхождение и контрольные суммы фиксируются в каталоге источников.
- Извлечение сначала использует текстовый слой PDF и включает OCR только при недостаточном объёме текста.
- PDF skill Anthropic не устанавливается из-за ограничений его опубликованной лицензии; используется OpenAI PDF skill и воспроизводимые CLI-инструменты.
- Runner строится гибридно: LLM планирует и мутирует сценарии, детерминированный слой выполняет шаги, фиксирует trace и проверяет последствия.
- Основной результат кейса описывается checkpoints `W1/W2/E1/E2/E3/F1/F2`; основной KPI — end-to-end ASR с доказанным внешним последствием.
- OpenRouter используется для атакуемого агента, будущих planner/mutator и semantic judge; Ollama — для offline smoke и резервного демо. Executor, IAM, evidence, programmatic oracles и метрики не зависят от LLM.
- Для MVP OpenRouter по умолчанию использует `openai/gpt-4.1-mini`: `gpt-5-mini` оставлен для матричных замеров, но 2026-09-06 нестабильно закреплял write-side факты как global policy на этом стенде.

## Блокеры

- Перед этапом 5 нужно согласовать допустимый бюджет OpenRouter и итоговую матрицу моделей/повторов.

## Ближайшие шаги

1. Подключить OpenRouter planner/mutator как генератор schema-valid сценариев.
2. Добавить первые варианты C1/C2/C3 payload families поверх campaign runner.
