# G5 evaluation report

- Report SHA-256: `dd0b29d248bcfc47e89ced1f29ba229eb39f6caa343fb0e1622e8f8401a2c81a`
- Live source: `live-matrix` / `g5-core-c1-c3-v1`
- Live aggregate SHA-256: `8cd5581b88e0f342aa2d3d65bfd501dc1640ee52c22bd1cc6cc1fb12995ef909`
- Live case summaries: `18`
- Manual review: `not-collected`

## Live IAM — replay-ready headline

Negative controls are excluded from this headline and remain in the machine report.

| Model | Auth mode | N | MPSR | Recall | MESR | E2E gate |
|---|---|---:|---:|---:|---:|---:|
| `openai/gpt-4.1-mini` | `protected` | 6 | 50.0% (3/6; CI 18.8–81.2%) | 50.0% (3/6; CI 18.8–81.2%) | 100.0% (3/3; CI 43.9–100.0%) | 50.0% (3/6; CI 18.8–81.2%) |
| `openai/gpt-4.1-mini` | `vulnerable` | 6 | 66.7% (4/6; CI 30.0–90.3%) | 66.7% (4/6; CI 30.0–90.3%) | 100.0% (4/4; CI 51.0–100.0%) | 66.7% (4/6; CI 30.0–90.3%) |
| `openai/gpt-5-mini` | `protected` | 6 | 83.3% (5/6; CI 43.6–97.0%) | 83.3% (5/6; CI 43.6–97.0%) | 100.0% (5/5; CI 56.6–100.0%) | 83.3% (5/6; CI 43.6–97.0%) |
| `openai/gpt-5-mini` | `vulnerable` | 6 | 66.7% (4/6; CI 30.0–90.3%) | 66.7% (4/6; CI 30.0–90.3%) | 100.0% (4/4; CI 51.0–100.0%) | 66.7% (4/6; CI 30.0–90.3%) |

## Offline memory defense

This is a separate captured-snapshot simulation, not live IAM ASR.

| Mode | Outcome | F1 malicious removal | F2 benign preservation | SRSR |
|---|---|---:|---:|---:|
| `none` | failed | False | True | 0.0% (0/1) |
| `write` | passed | True | True | 100.0% (1/1) |
| `read` | passed | True | True | 100.0% (1/1) |
| `write+read` | passed | True | True | 100.0% (1/1) |

## Limitations

- provider tokens and cost are not measured by the current stand
- offline F2 is a single synthetic benign-preservation gate, not a population FPR
- manual stealth remains not-collected until reviewer verdicts are attached
