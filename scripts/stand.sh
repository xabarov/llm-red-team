#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
stand_dir="$project_root/.cache/agent-memory-stand"
lock_file="$project_root/infra/stand.lock"
env_template="$project_root/infra/stand.env.example"
ollama_override="$project_root/infra/stand.ollama.yml"
openrouter_override="$project_root/infra/stand.openrouter.yml"
root_env="$project_root/.env"
provider_state="$project_root/.cache/stand-llm-provider"

requested_provider="${2:-${STAND_LLM_PROVIDER:-auto}}"

root_openrouter_key_is_set() {
  [[ -f "$root_env" ]] || return 1
  local value
  value=$(awk -F= '
    /^[[:space:]]*OPENROUTER_API_KEY[[:space:]]*=/ {
      sub(/^[^=]*=/, "")
      gsub(/^[[:space:]]+|[[:space:]]+$/, "")
      print
      exit
    }
  ' "$root_env")
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  [[ -n "$value" ]]
}

resolve_provider() {
  local candidate="$requested_provider"

  if [[ "$candidate" == "auto" && -f "$provider_state" ]]; then
    candidate=$(<"$provider_state")
  fi
  if [[ "$candidate" == "auto" ]]; then
    if root_openrouter_key_is_set; then
      candidate="openrouter"
    else
      candidate="ollama"
    fi
  fi
  if [[ "$candidate" != "openrouter" && "$candidate" != "ollama" ]]; then
    printf 'Unknown LLM provider: %s (expected openrouter, ollama, or auto)\n' "$candidate" >&2
    exit 2
  fi
  if [[ "$candidate" == "openrouter" ]] && ! root_openrouter_key_is_set; then
    printf 'OPENROUTER_API_KEY is missing or empty in %s\n' "$root_env" >&2
    exit 1
  fi
  printf '%s' "$candidate"
}

provider=$(resolve_provider)

# shellcheck disable=SC1090
source "$lock_file"

compose() {
  local args=(
    docker compose
    --project-name agent-memory-stand
    --project-directory "$stand_dir"
  )

  if [[ "$provider" == "openrouter" ]]; then
    args+=(--env-file "$root_env" -f "$stand_dir/docker-compose.yml" -f "$openrouter_override")
  else
    args+=(-f "$stand_dir/docker-compose.yml" -f "$ollama_override")
  fi

  "${args[@]}" "$@"
}

bootstrap() {
  if [[ ! -d "$stand_dir/.git" ]]; then
    mkdir -p "$(dirname "$stand_dir")"
    git clone "$STAND_REPOSITORY" "$stand_dir"
  fi

  current_origin=$(git -C "$stand_dir" remote get-url origin)
  [[ "$current_origin" == "$STAND_REPOSITORY" ]] || {
    printf 'Unexpected stand origin: %s\n' "$current_origin" >&2
    exit 1
  }

  if [[ -n "$(git -C "$stand_dir" status --porcelain)" ]]; then
    printf 'Stand checkout has local changes; refusing to switch revision.\n' >&2
    exit 1
  fi

  git -C "$stand_dir" fetch --quiet origin "$STAND_REVISION"
  git -C "$stand_dir" checkout --quiet --detach "$STAND_REVISION"

  if [[ ! -f "$stand_dir/.env" ]]; then
    cp "$env_template" "$stand_dir/.env"
  fi

  mkdir -p "$stand_dir/keycloak/certs"
  if [[ ! -f "$stand_dir/keycloak/certs/tls.key" || ! -f "$stand_dir/keycloak/certs/tls.crt" ]]; then
    openssl req -x509 -newkey rsa:2048 -nodes \
      -keyout "$stand_dir/keycloak/certs/tls.key" \
      -out "$stand_dir/keycloak/certs/tls.crt" \
      -days 3650 -subj "/CN=localhost" \
      -addext "subjectAltName=DNS:localhost,DNS:keycloak,IP:127.0.0.1" \
      >/dev/null 2>&1
  fi

  compose config --quiet
  printf 'Stand prepared at %s (%s)\n' "$stand_dir" "$STAND_REVISION"
}

smoke() {
  local deadline=$((SECONDS + 300))
  local endpoints=(
    "http://localhost:8600/healthz"
    "http://localhost:8180/realms/genai-stand/.well-known/openid-configuration"
  )
  if [[ "$provider" == "ollama" ]]; then
    endpoints+=("http://localhost:11434/api/tags")
  fi

  while (( SECONDS < deadline )); do
    local ready=1
    for endpoint in "${endpoints[@]}"; do
      if ! curl --fail --silent --show-error "$endpoint" >/dev/null 2>&1; then
        ready=0
        break
      fi
    done
    if (( ready == 1 )); then
      compose ps
      printf 'Smoke test passed (LLM provider: %s).\n' "$provider"
      return 0
    fi
    sleep 5
  done

  compose ps
  printf 'Smoke test timed out. Inspect with: make stand-logs\n' >&2
  return 1
}

case "${1:-}" in
  bootstrap)
    bootstrap
    ;;
  up)
    bootstrap
    compose up -d --build --remove-orphans
    printf '%s\n' "$provider" > "$provider_state"
    smoke
    ;;
  down)
    compose down --remove-orphans
    if [[ -f "$provider_state" ]]; then
      unlink "$provider_state"
    fi
    ;;
  status)
    compose ps
    ;;
  logs)
    compose logs --tail=200
    ;;
  smoke)
    smoke
    ;;
  *)
    printf 'Usage: %s {bootstrap|up|down|status|logs|smoke} [openrouter|ollama|auto]\n' "$0" >&2
    exit 2
    ;;
esac
