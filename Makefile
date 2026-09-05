.PHONY: doctor context-check stand-bootstrap stand-up stand-up-openrouter stand-up-local stand-down stand-status stand-logs stand-smoke stand-agent-smoke stage1-test stage1-run scenario-validate campaign-run

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

scenario-validate:
	@PYTHONPATH=src uv run python scripts/run-campaign.py --validate-only

campaign-run:
	@PYTHONPATH=src uv run python scripts/run-campaign.py --freeze
