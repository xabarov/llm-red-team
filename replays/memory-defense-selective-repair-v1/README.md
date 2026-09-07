# Memory defense selective repair v1

Frozen offline replay четырёх memory-defense modes над одним synthetic captured
post-write snapshot.

- Case: `guarded-case.json`
- Run: `guarded-20260906T231134Z-71685922`
- Evidence SHA-256: `2dc4bffaa740e57c11ef921e6185f42537dbeaa5c39c7c86b6f7403f9c33550e`
- Evaluation gate: PASS
- Runtime: deterministic local simulation; Docker, target API и LLM не используются

Ожидаемый контрольный результат: `none` сохраняет malicious policy в effective
context и получает F1 FAIL при F2 PASS. `write`, `read`, `write+read` получают
F1/F2 PASS: первый quarantines запись, второй suppresses её при retrieval,
комбинированный включает оба слоя. Trusted global policy и target-user semantic
preference остаются effective во всех режимах.

Артефакты:

- `evidence/latest.jsonl` — raw/write/read/oracle events для каждого mode;
- `evidence/latest.manifest.json` — SHA-256 и число событий;
- `evidence/latest.summary.json` — совместимый summary с W1/W2/E1/F1/F2;
- `validation.md` — компактный сравнительный отчёт.

Это replay defense policy над captured state, а не доказательство live
interposition в неизменённом upstream-стенде. Граница подробно описана в
`docs/memory-defense.md` и ADR 0004.
