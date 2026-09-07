# 0004. Memory-defense как отдельный offline evaluation layer

- Статус: accepted
- Дата: 2026-09-07

## Контекст

Текущий campaign `mode` управляет IAM стенда (`vulnerable` или `protected`).
Write/retrieval defense — другая ось эксперимента. Upstream не предоставляет
hook, который позволил бы подменить policy snapshot или prompt context перед
реальным agent turn. Изменение только копии контекста в evaluator создало бы
ложное доказательство защиты.

## Решение

Для G4 вводится отдельный deterministic evaluation layer над captured
post-write snapshot. Он сохраняет raw snapshot, затем моделирует четыре режима:
`none`, `write`, `read`, `write+read`. Write gate и selective repair используют
provenance/authority и scope; retrieval gate строит target-scoped effective
context и подавляет недоверенные global policy instructions. Oracle labels и
текстовые canary terms не участвуют в решении защиты.

Результат имеет совместимый case-summary формат и checkpoints W1/W2/E1/F1/F2,
поэтому G3 считает SRSR. Это доказательство корректности defense policy над
зафиксированным состоянием, а не утверждение, что upstream уже исполняет guard.
Для end-to-end live comparison позже потребуется явный interposition hook или
fork/adapter стенда.

## Последствия

Baseline replay и auth modes остаются без изменений. Все четыре defense modes
сравниваются на идентичном синтетическом snapshot без LLM и сети. Raw evidence
не уничтожается; quarantine/suppression видны отдельно. Ограничение simulation
явно показывается в отчёте и документации.

## Альтернативы

- Переиспользовать `auth_mode`: смешивает IAM и memory defense, ломает смысл
  существующих oracles.
- Фильтровать только evaluator context в campaign runner: создаёт ложный PASS,
  потому что атакуемый агент всё равно видел исходную память.
- Патчить upstream прямо сейчас: даёт live hook, но связывает G4 с конкретной
  реализацией стенда и увеличивает риск поломки базового replay.
