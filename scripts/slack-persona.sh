#!/usr/bin/env bash
# Send a Slack message as a specific Paperwork Labs persona.
#
# Usage:
#   ./scripts/slack-persona.sh <persona> <channel> <message>
#   ./scripts/slack-persona.sh engineering C0ALLEKR9FZ "PR #18 merged"
#   ./scripts/slack-persona.sh ea C0ALLJWR1HV "Good morning! Here's today's briefing..."
#
# Personas: ea, engineering, strategy, legal, cfo, qa, growth, social,
#           tax, cpa, partnerships, agent-ops, general
#
# Requires SLACK_BOT_TOKEN in .env.local or environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

if [[ -z "${SLACK_BOT_TOKEN:-}" ]]; then
  if [[ -f "$ROOT_DIR/.env.local" ]]; then
    export "$(grep SLACK_BOT_TOKEN "$ROOT_DIR/.env.local" | xargs)"
  fi
fi

if [[ -z "${SLACK_BOT_TOKEN:-}" ]]; then
  echo "Error: SLACK_BOT_TOKEN not set. Add it to .env.local or export it." >&2
  exit 1
fi

PERSONA="${1:?Usage: slack-persona.sh <persona> <channel> <message>}"
CHANNEL="${2:?Usage: slack-persona.sh <persona> <channel> <message>}"
MESSAGE="${3:?Usage: slack-persona.sh <persona> <channel> <message>}"
THREAD_TS="${4:-}"

case "$PERSONA" in
  ea|operator)
    USERNAME="EA / Operator"
    ICON=":clipboard:"
    ;;
  engineering|eng)
    USERNAME="Engineering"
    ICON=":gear:"
    ;;
  strategy)
    USERNAME="Strategy"
    ICON=":chess_pawn:"
    ;;
  legal)
    USERNAME="Legal"
    ICON=":scales:"
    ;;
  cfo|finance)
    USERNAME="Finance"
    ICON=":chart_with_upwards_trend:"
    ;;
  qa)
    USERNAME="QA"
    ICON=":mag:"
    ;;
  growth)
    USERNAME="Growth"
    ICON=":rocket:"
    ;;
  social)
    USERNAME="Social"
    ICON=":speech_balloon:"
    ;;
  tax|tax-domain)
    USERNAME="Tax Domain"
    ICON=":receipt:"
    ;;
  cpa)
    USERNAME="CPA Advisor"
    ICON=":bar_chart:"
    ;;
  partnerships)
    USERNAME="Partnerships"
    ICON=":handshake:"
    ;;
  agent-ops)
    USERNAME="Agent Ops"
    ICON=":robot_face:"
    ;;
  *)
    USERNAME="Paperwork AI"
    ICON=":bulb:"
    ;;
esac

PAYLOAD=$(python3 -c "
import json, sys
d = {
    'channel': sys.argv[1],
    'text': sys.argv[2],
    'username': sys.argv[3],
    'icon_emoji': sys.argv[4]
}
if sys.argv[5]:
    d['thread_ts'] = sys.argv[5]
print(json.dumps(d))
" "$CHANNEL" "$MESSAGE" "$USERNAME" "$ICON" "$THREAD_TS")

RESPONSE=$(curl -s -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d "$PAYLOAD")

OK=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('ok','false'))")

if [[ "$OK" == "True" ]]; then
  TS=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ts',''))")
  CH=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('channel',''))")
  echo "https://paperwork-labs.slack.com/archives/$CH/p${TS//./}"
else
  ERROR=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error','unknown'))")
  echo "Error: $ERROR" >&2
  exit 1
fi
