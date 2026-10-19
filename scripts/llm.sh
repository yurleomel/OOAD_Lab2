#!/usr/bin/env bash
# Call Bedrock from the laptop, through the backend's dev container (which has
# the anthropic SDK): the first call of Lab 6, and the agenda parser on its own.
#
#   ./scripts/llm.sh hello            make llm-hello
#   TEXT="..." ./scripts/llm.sh parse make parse TEXT="..."
#
# The container gets the same AWS credentials the deploy scripts use: AWS_* from
# .env or the shell, and ~/.aws (read-only) for profiles and SSO.
# PARSER_MODEL=us.anthropic.claude-sonnet-4-6 tries another model; PARSER_API=messages
# with PARSER_MODEL=anthropic.claude-opus-5-5 is the lab's own (bedrock-mantle).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"

die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

if [[ -f "${ENV_FILE}" ]]; then
  preset="$(export -p)"
  set -a
  # shellcheck disable=SC1091
  source "${ENV_FILE}"
  set +a
  eval "${preset}"
fi

args=(run --rm --no-deps -e APP_ENV=development -e BEDROCK_REGION="${AWS_REGION:-us-east-1}")
for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN PARSER_API PARSER_MODEL; do
  # A blank AWS_PROFILE would be read as a profile named "": pass only what is set.
  [[ -n "${!var:-}" ]] && args+=(-e "${var}=${!var}")
done
[[ -d "${HOME}/.aws" ]] && args+=(-v "${HOME}/.aws:/root/.aws:ro")

case "${1:-}" in
  hello) exec docker compose "${args[@]}" backend python -m app.ai.hello ;;
  parse)
    [[ -n "${TEXT:-}" ]] || die 'usage: make parse TEXT="Пн 10:00, синк по прайсингу, 45 хв. ..."'
    exec docker compose "${args[@]}" backend python -m app.ai.agenda "${TEXT}"
    ;;
  *) die "usage: $0 hello|parse" ;;
esac
