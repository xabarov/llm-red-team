.PHONY: doctor context-check stand-bootstrap stand-up stand-up-openrouter stand-up-local stand-down stand-status stand-logs stand-smoke stand-agent-smoke

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
