# Активные задачи

## HACK-009 — G5 Evaluation Matrix

- Этап: 5 — воспроизводимая evaluation matrix и защищаемые агрегаты.
- Результат: зафиксированы model × auth mode × defense mode × attack class × carrier × seed, повторы, бюджеты, blinded manual review и правила восстановления метрик из evidence.
- Готово, когда: matrix plan и budget estimate согласованы, runner воспроизводим, а измеренные и предполагаемые cost/latency явно разделены.
- Контекст: G4 дал offline `none/write/read/write+read` replay и SRSR; live interposition ещё не реализован и не должен смешиваться с simulation results.
- Блокер: proposed plan готов, но до платных OpenRouter runs нужно явно утвердить `gpt-4.1-mini` + `gpt-5-mini`, 3 повтора и hard cap `$20`.
- Ближайшее действие: после approval переключить `evaluation/matrix.yaml` в `approved`, подтвердить новый plan SHA-256 и выполнить `make evaluation-run` с `--execute`.
