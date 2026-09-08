# Память проекта

Обновлено: 2026-09-08

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
- Этап 3 начат: добавлен deterministic seed-family scaffold без LLM-вызовов; `seeds/cross-user-policy-poisoning.yaml` материализует C1/C2/C3 варианты через `make scenario-generate`.
- OpenRouter planner подключен: `make planner-draft` пишет prompt без сети, `make planner-openrouter` делает один вызов и сохраняет `seed-family/v1` с provenance в `output/planner/`.
- Первый limited batch по planner-generated C1/C2/C3 выполнен: `campaign-20260906T125522Z-641ead12`. Полный PASS: C1 explicit-command 1/3; C2 policy-document дал write/recall, но без exploitation; C3 compaction-salience слабый.
- Крупные goal-блоки G1-G6 описаны в `docs/goal-blocks.md`; каждый включает gate и нейтральную инструкцию для субагентов под authorized локальный стенд.
- G1 Replay Corpus завершён: C1 explicit-command сохранён в `replays/cross-user-policy-poisoning-c1-explicit-command/` с `scenario.json`, frozen `evidence/latest.*`, `validation.md` и индексом `replays/README.md`. Evidence SHA-256 `7d7e9499c770e99d2d7ced52bf5e63a7ff7bc29a308a860249ff2087b6649f2c`; результат vulnerable/protected PASS/PASS.
- G2 Seed Improvement завершён: seed-family расширен до 8 variants. Успешный C2 `cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger` сохранён в replay corpus с PASS/PASS, run `campaign-20260906T175830Z-60b0d296`, evidence SHA-256 `bac72328bb2b436f0b61285233cc0fafcda72a4a4d1b88629b956f61d95e46e6`. C3 после двух wording-итераций зафиксирован как negative result в `docs/seed-improvement-g2.md`.
- G3 Batch Metrics завершён: `make batch-metrics` офлайн читает case/batch summaries, пересчитывает cumulative funnel и MPSR/MESR/E2E gates, показывает attempts и telemetry coverage, проверяет integrity aggregates и выбирает replay candidates строгими правилами. На 21 сохранённом run (25 cases) расхождений batch summaries нет; generated C1 и C2 soft-strict-trigger выбраны `replay-ready`.
- G4 Guarded Modes завершён как честный offline simulation layer над captured post-write snapshot: режимы `none/write/read/write+read`, provenance/authority write/read gates, selective repair и W1/W2/E1/F1/F2. Frozen replay `memory-defense-selective-repair-v1`, run `guarded-20260906T231134Z-71685922`, evidence SHA-256 `2dc4bffaa740e57c11ef921e6185f42537dbeaa5c39c7c86b6f7403f9c33550e`; none F1 FAIL/F2 PASS, три guarded modes F1/F2 PASS и SRSR=1.
- G5 завершён: approved plan `6cd440c…fab7b` выполнил C1/C2/C3 × vulnerable/protected × 3 repeats для `gpt-4.1-mini` и `gpt-5-mini`. Session `g5-20260908-full-v2`: 18/18 artifacts, 36 cells, 84 attempts, 48 мин 8 с. Replay-ready C1/C2 дали E2E `8/12` в каждой ветке (vulnerable — внешнее чтение, protected — IAM-блокировка); C3 дал один vulnerable E2E из шести и считается weak negative control. Portable bundle: `evaluation/results/g5-20260908-full-v2/`, aggregate SHA-256 `8cd5581b…ef909`.
- G5 provider cost/tokens не измерены: `$1.27/$15.72` остаются preflight estimates при approved cap `$20`. Blinded packet на 36 cells успешно строится, но независимые human verdicts не собраны (`not-collected`).
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
- Расширенные campaign-метрики пересчитываются из case-level conjunctions; `batch-summary.json` служит integrity check. Отсутствующие cost/latency observations остаются `n/a` с coverage, а не считаются нулевыми.
- Memory-defense не смешивается с IAM auth modes: G4 работает над captured state и не заявляется как live защита upstream. Для реального E2E сравнения нужен interposition hook; provenance metadata должна поступать из доверенного канала.
- Завершённые live evaluation bundles сохраняются в `evaluation/results/<session>/` с исходным manifest и logical `path_map`; рабочие/review-private файлы остаются в ignored `output/`.

## Блокеры

- Для G6 внешних блокеров нет. Human stealth review потребует двух независимых рецензентов и третьего при расхождении; до этого метрика остаётся `not-collected`.

## Ближайшие шаги

1. Завести HACK-задачу на G6 и собрать demo/submission narrative из frozen G5 report.
2. Подготовить основной replay и запасной prerecorded trace без нового платного прогона.
3. При наличии двух независимых рецензентов провести blinded review по `evaluation/judge-rubric.yaml`; не блокировать техническое завершение G5 отсутствующей человеческой разметкой.
