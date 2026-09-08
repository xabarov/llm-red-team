.PHONY: doctor context-check stand-bootstrap stand-up stand-up-openrouter
.PHONY: stand-up-local stand-down stand-status stand-logs stand-smoke stand-agent-smoke
.PHONY: stage1-test stage1-run planner-draft planner-openrouter scenario-generate
.PHONY: scenario-validate campaign-run batch-metrics guarded-validate guarded-eval
.PHONY: evaluation-plan evaluation-run evaluation-report evaluation-review-prepare
.PHONY: evaluation-combined-report

doctor:
	@bash scripts/doctor.sh

context-check:
	@bash scripts/context-check.sh

stand-bootstrap:
	@bash scripts/stand.sh bootstrap

stand-up:
	@bash scripts/stand.sh up

stand-up-openrouter:
	@bash scripts/stand.sh up openrouter

stand-up-local:
	@bash scripts/stand.sh up ollama

stand-down:
	@bash scripts/stand.sh down

stand-status:
	@bash scripts/stand.sh status

stand-logs:
	@bash scripts/stand.sh logs

stand-smoke:
	@bash scripts/stand.sh smoke

stand-agent-smoke:
	@bash scripts/stand-agent-smoke.sh

stage1-test:
	@PYTHONPATH=src uv run python -m unittest discover -s tests

stage1-run:
	@PYTHONPATH=src uv run python scripts/run-stage1.py --freeze

planner-draft:
	@PYTHONPATH=src uv run python scripts/plan-seed-family.py

planner-openrouter:
	@PYTHONPATH=src uv run python scripts/plan-seed-family.py --call-openrouter

scenario-generate:
	@PYTHONPATH=src uv run python scripts/generate-scenarios.py

scenario-validate:
	@PYTHONPATH=src uv run python scripts/run-campaign.py --validate-only

campaign-run:
	@PYTHONPATH=src uv run python scripts/run-campaign.py --freeze

batch-metrics:
	@PYTHONPATH=src uv run python scripts/report-metrics.py $(METRICS_ARGS)

guarded-validate:
	@PYTHONPATH=src uv run python scripts/run-guarded-eval.py --validate-only

guarded-eval:
	@PYTHONPATH=src uv run python scripts/run-guarded-eval.py $(GUARDED_ARGS)

evaluation-plan:
	@PYTHONPATH=src uv run python scripts/plan-evaluation.py $(EVALUATION_ARGS)

evaluation-run:
	@PYTHONPATH=src uv run python scripts/run-evaluation.py $(EVALUATION_ARGS)

evaluation-report:
	@PYTHONPATH=src uv run python scripts/report-evaluation.py \
		$(or $(EVALUATION_MANIFEST),evaluation/historical-execution-manifest.json) $(EVALUATION_ARGS)

evaluation-review-prepare:
	@PYTHONPATH=src uv run python scripts/prepare-review.py \
		$(or $(EVALUATION_MANIFEST),evaluation/historical-execution-manifest.json) \
		--output-dir $(or $(REVIEW_OUTPUT_DIR),output/reviews/current)

evaluation-combined-report:
	@PYTHONPATH=src uv run python scripts/build-evaluation-report.py \
		$(or $(EVALUATION_MANIFEST),evaluation/historical-execution-manifest.json) $(EVALUATION_ARGS)
