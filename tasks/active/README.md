# Активные задачи

## HACK-005 — Обобщить replay в scenario engine

- Этап: 2 — детерминированный scenario engine.
- Результат: YAML/JSON сценарии запускаются через общий campaign runner с теми же evidence/oracles.
- Готово, когда: `cross-user-policy-poisoning-v1` работает через schema-valid DSL, а batch runner выдаёт case-level отчёты.
- Ближайшее действие: выделить schema для setup/inject/persist/trigger/verify/cleanup поверх текущего stage1 runner.
