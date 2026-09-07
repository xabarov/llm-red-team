# Активные задачи

## HACK-009 — G5 Evaluation Matrix

- Этап: 5 — воспроизводимая evaluation matrix и защищаемые агрегаты.
- Результат: зафиксированы model × auth mode × defense mode × attack class × carrier × seed, повторы, бюджеты и правила восстановления метрик из evidence.
- Готово, когда: matrix plan и budget estimate согласованы, runner воспроизводим, а измеренные и предполагаемые cost/latency явно разделены.
- Контекст: G4 дал offline `none/write/read/write+read` replay и SRSR; live interposition ещё не реализован и не должен смешиваться с simulation results.
- Блокер: до платных OpenRouter runs требуется согласовать бюджет и итоговый список моделей/повторов.
- Ближайшее действие: построить бесплатный matrix plan и budget estimate из уже сохранённых summaries, не запуская платные прогоны.
