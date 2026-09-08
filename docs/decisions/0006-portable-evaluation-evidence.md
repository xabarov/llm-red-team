# ADR-0006: Portable evaluation evidence через logical path map

- Статус: принято
- Дата: 2026-09-08

## Контекст

Live runner пишет артефакты в ignored `output/`, а execution manifest намеренно
сохраняет точные logical paths approved run. Простое перемещение файлов меняет
пути и лишает reporter возможности пересобрать исходный plan и проверить все
hashes в чистом clone.

## Решение

После полной проверки live manifest команда `evaluation-freeze` копирует matrix
snapshot, pinned inputs, calibration и case evidence в
`evaluation/results/<session>/`. Frozen manifest не переписывает исходные пути:
он добавляет `path_map` из logical path в immutable tracked copy, SHA-256
исходного manifest и время заморозки.

Reporter и blinded-review builder разрешают пути только через этот map, повторно
проверяют, что и logical, и mapped path не выходят из repository root, а затем
выполняют прежнюю полную hash/evidence validation. Исходный manifest сохраняется
байт-в-байт рядом с frozen manifest.

Для активного matrix contract компактный `evaluation/input-path-map.json`
разрешает те же immutable calibration copies при dry-run и новом execution. Map
не входит в семантический plan hash, поскольку каждый target всё равно проверен
content hash из matrix; source execution manifest сохраняет использованный map.

## Последствия

Результат можно пересчитать без ignored `output/` и без нового доступа к стенду
или модели, сохранив exact approved plan hash. Bundle занимает больше места в
Git, поэтому замораживаются только завершённые матрицы, а review packet, private
mapping и незавершённые sessions остаются в `output/`.
