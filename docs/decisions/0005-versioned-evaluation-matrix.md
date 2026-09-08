# ADR-0005: Versioned evaluation matrix and explicit paid-run approval

- Статус: принято
- Дата: 2026-09-08

## Контекст

Live campaign использует платный внешний backend, а исторические summaries не
содержат provider token/cost telemetry. Одновременно защита требует, чтобы
матрица была воспроизводимой, а агрегаты проверялись по исходному evidence.

## Решение

Матрица хранится как schema-validated YAML с hashes всех входов и pinned stand
revision. Dry-run всегда разрешён. Live запуск требует одновременно:

- `status: approved`;
- `budget.approved: true` и числовой `hard_cap_usd`;
- conservative estimate не выше cap;
- переданный оператором точный SHA-256 текущего плана.

Каждый запуск создаёт execution manifest с model/repeat и hashes summary,
evidence и evidence manifest, а также snapshot точной matrix. Финальный
aggregate строится только после повторной сборки plan из snapshot, сверки обеих
runtime-моделей/revision стенда, проверки evidence-цепочки и полноты artifacts.

Live auth modes и offline memory-defense modes остаются отдельными треками.

## Последствия

Любое изменение модели, цены, assumptions, сценария или числа повторов меняет
plan hash и требует нового явного approval. Preflight cap защищает от запуска
заведомо слишком большой матрицы, но без runtime usage telemetry не является
лимитом фактического счёта OpenRouter; это ограничение указывается в отчёте.
