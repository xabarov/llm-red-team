# Разборы научных статей на русском

Каждая публикация находится в отдельной папке со стабильным `id` из
`research/sources.yaml`. Внутри лежит компактный `summary.md`: суть, методика,
численные результаты, ограничения, применение к хакатону и карта всех страниц
PDF. Полные машинные переводы намеренно не хранятся.

| Публикация | Русская версия | Статус |
|---|---|---|
| From Untrusted Input to Trusted Memory | [`summary.md`](untrusted-input-trusted-memory-2606.04329/summary.md) | Каналы записи, уязвимости, taxonomy и MPBench |
| When Agents Remember Too Much | [`summary.md`](agents-remember-too-much-2607.06595/summary.md) | GhostWriter, delayed activation и AM-Sentry |
| MemSecBench | [`summary.md`](memsecbench-2607.27080/summary.md) | Полный lifecycle, evidence protocol и selective repair |

Pipeline не применяет OCR без необходимости: сначала он измеряет качество
встроенного текстового слоя. Все три текущих PDF имеют пригодный текстовый слой,
поэтому повторное распознавание только ухудшило бы формулы и библиографию. Для
сканированных PDF подготовлен Tesseract fallback (`eng`/`rus`).

Источники, версии, лицензии и контрольные суммы указаны в
[`../../sources.yaml`](../../sources.yaml). Единая терминология для будущих
материалов находится в [`../../glossary.md`](../../glossary.md).

Рекомендуемый порядок чтения: taxonomy → реалистичная атака и защита → строгая
оценка полного жизненного цикла.
