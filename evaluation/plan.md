# Evaluation plan: g5-core-c1-c3-v1

- Status: `proposed`
- Plan SHA-256: `573e8d642df94cecc8b1ac55e02b18516de88b621c9cf16619eb5b76b7b0c95a`
- Live scenario runs / mode cells: `18` / `36`
- Expected / maximum attempts: `84` / `108`
- Expected / maximum LLM calls: `504` / `1836` (assumed)
- Historical-duration extrapolation: `1472.2s` (stand restarts excluded)
- Estimated / maximum estimated cost: `$1.27` / `$15.72`
- Budget: `not approved`; hard cap: `n/a`; proposed cap: `$20.00`
- Maximum live wall time: `7200s`
- Cost and call counts are estimates; existing evidence has no provider token/cost telemetry.
- Offline memory-defense is a separate track and is not a live auth-mode comparison.

## Per-model estimate

| Model | Cells | Attempts exp/max | Calls exp/max | Cost exp/max, USD |
|---|---:|---:|---:|---:|
| `openai/gpt-4.1-mini` | 18 | 42/54 | 252/918 | 0.71/8.52 |
| `openai/gpt-5-mini` | 18 | 42/54 | 252/918 | 0.57/7.20 |

## Cells

| Model | Class | Carrier | Scenario | Mode | Repeat | Maturity |
|---|---|---|---|---|---:|---|
| `openai/gpt-4.1-mini` | C1 | `direct-policy-command` | `cross-user-policy-poisoning-c1-explicit-command` | `vulnerable` | 1 | replay-ready |
| `openai/gpt-4.1-mini` | C1 | `direct-policy-command` | `cross-user-policy-poisoning-c1-explicit-command` | `protected` | 1 | replay-ready |
| `openai/gpt-4.1-mini` | C1 | `direct-policy-command` | `cross-user-policy-poisoning-c1-explicit-command` | `vulnerable` | 2 | replay-ready |
| `openai/gpt-4.1-mini` | C1 | `direct-policy-command` | `cross-user-policy-poisoning-c1-explicit-command` | `protected` | 2 | replay-ready |
| `openai/gpt-4.1-mini` | C1 | `direct-policy-command` | `cross-user-policy-poisoning-c1-explicit-command` | `vulnerable` | 3 | replay-ready |
| `openai/gpt-4.1-mini` | C1 | `direct-policy-command` | `cross-user-policy-poisoning-c1-explicit-command` | `protected` | 3 | replay-ready |
| `openai/gpt-4.1-mini` | C2 | `policy-document` | `cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger` | `vulnerable` | 1 | replay-ready |
| `openai/gpt-4.1-mini` | C2 | `policy-document` | `cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger` | `protected` | 1 | replay-ready |
| `openai/gpt-4.1-mini` | C2 | `policy-document` | `cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger` | `vulnerable` | 2 | replay-ready |
| `openai/gpt-4.1-mini` | C2 | `policy-document` | `cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger` | `protected` | 2 | replay-ready |
| `openai/gpt-4.1-mini` | C2 | `policy-document` | `cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger` | `vulnerable` | 3 | replay-ready |
| `openai/gpt-4.1-mini` | C2 | `policy-document` | `cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger` | `protected` | 3 | replay-ready |
| `openai/gpt-4.1-mini` | C3 | `compaction-summary` | `cross-user-policy-poisoning-c3-compaction-neutral-summary` | `vulnerable` | 1 | negative-control |
| `openai/gpt-4.1-mini` | C3 | `compaction-summary` | `cross-user-policy-poisoning-c3-compaction-neutral-summary` | `protected` | 1 | negative-control |
| `openai/gpt-4.1-mini` | C3 | `compaction-summary` | `cross-user-policy-poisoning-c3-compaction-neutral-summary` | `vulnerable` | 2 | negative-control |
| `openai/gpt-4.1-mini` | C3 | `compaction-summary` | `cross-user-policy-poisoning-c3-compaction-neutral-summary` | `protected` | 2 | negative-control |
| `openai/gpt-4.1-mini` | C3 | `compaction-summary` | `cross-user-policy-poisoning-c3-compaction-neutral-summary` | `vulnerable` | 3 | negative-control |
| `openai/gpt-4.1-mini` | C3 | `compaction-summary` | `cross-user-policy-poisoning-c3-compaction-neutral-summary` | `protected` | 3 | negative-control |
| `openai/gpt-5-mini` | C1 | `direct-policy-command` | `cross-user-policy-poisoning-c1-explicit-command` | `vulnerable` | 1 | replay-ready |
| `openai/gpt-5-mini` | C1 | `direct-policy-command` | `cross-user-policy-poisoning-c1-explicit-command` | `protected` | 1 | replay-ready |
| `openai/gpt-5-mini` | C1 | `direct-policy-command` | `cross-user-policy-poisoning-c1-explicit-command` | `vulnerable` | 2 | replay-ready |
| `openai/gpt-5-mini` | C1 | `direct-policy-command` | `cross-user-policy-poisoning-c1-explicit-command` | `protected` | 2 | replay-ready |
| `openai/gpt-5-mini` | C1 | `direct-policy-command` | `cross-user-policy-poisoning-c1-explicit-command` | `vulnerable` | 3 | replay-ready |
| `openai/gpt-5-mini` | C1 | `direct-policy-command` | `cross-user-policy-poisoning-c1-explicit-command` | `protected` | 3 | replay-ready |
| `openai/gpt-5-mini` | C2 | `policy-document` | `cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger` | `vulnerable` | 1 | replay-ready |
| `openai/gpt-5-mini` | C2 | `policy-document` | `cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger` | `protected` | 1 | replay-ready |
| `openai/gpt-5-mini` | C2 | `policy-document` | `cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger` | `vulnerable` | 2 | replay-ready |
| `openai/gpt-5-mini` | C2 | `policy-document` | `cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger` | `protected` | 2 | replay-ready |
| `openai/gpt-5-mini` | C2 | `policy-document` | `cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger` | `vulnerable` | 3 | replay-ready |
| `openai/gpt-5-mini` | C2 | `policy-document` | `cross-user-policy-poisoning-c2-policy-document-soft-strict-trigger` | `protected` | 3 | replay-ready |
| `openai/gpt-5-mini` | C3 | `compaction-summary` | `cross-user-policy-poisoning-c3-compaction-neutral-summary` | `vulnerable` | 1 | negative-control |
| `openai/gpt-5-mini` | C3 | `compaction-summary` | `cross-user-policy-poisoning-c3-compaction-neutral-summary` | `protected` | 1 | negative-control |
| `openai/gpt-5-mini` | C3 | `compaction-summary` | `cross-user-policy-poisoning-c3-compaction-neutral-summary` | `vulnerable` | 2 | negative-control |
| `openai/gpt-5-mini` | C3 | `compaction-summary` | `cross-user-policy-poisoning-c3-compaction-neutral-summary` | `protected` | 2 | negative-control |
| `openai/gpt-5-mini` | C3 | `compaction-summary` | `cross-user-policy-poisoning-c3-compaction-neutral-summary` | `vulnerable` | 3 | negative-control |
| `openai/gpt-5-mini` | C3 | `compaction-summary` | `cross-user-policy-poisoning-c3-compaction-neutral-summary` | `protected` | 3 | negative-control |
