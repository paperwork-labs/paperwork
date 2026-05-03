# Cursor Hooks — Paperwork Labs

Project-level Cursor hooks that enforce operating doctrine at the tool layer.
Configured in `.cursor/hooks.json`.

## Active Hooks

### `enforce-cheap-agent-model.sh` — subagentStart

**Event:** `subagentStart`
**failClosed:** `true`

Enforces the PR T-Shirt Sizing taxonomy (Wave L). Validates that every Task (subagent) dispatch:

1. Includes a `model` field in the dispatch payload.
2. The model is in the allowed cheap-model list (XS–L only).
3. The model does NOT contain "opus" (Opus is forbidden as a subagent).

If any check fails, returns `{"permission":"deny", "user_message": "<remediation>"}` and blocks the dispatch.

**Allow-list:**

| Model slug | Size | Est. cost |
|-----------|------|-----------|
| `composer-1.5` | XS | ~$0.10 |
| `composer-2-fast` | S | ~$0.40 |
| `gpt-5.5-medium` | M | ~$1.00 |
| `claude-4.6-sonnet-medium-thinking` | L | ~$3.00 |

**Blocked:** Any model containing "opus" (XL — orchestrator only).

**Doctrine:** `.cursor/rules/cheap-agent-fleet.mdc` Rule #2
**Canonical reference:** `docs/PR_TSHIRT_SIZING.md`

### Testing locally

```bash
# Should deny — Opus model
echo '{"model":"claude-4.5-opus-high-thinking"}' | bash .cursor/hooks/enforce-cheap-agent-model.sh

# Should deny — missing model
echo '{"task":"do something"}' | bash .cursor/hooks/enforce-cheap-agent-model.sh

# Should allow — valid cheap model
echo '{"model":"composer-1.5"}' | bash .cursor/hooks/enforce-cheap-agent-model.sh
echo '{"model":"claude-4.6-sonnet-medium-thinking"}' | bash .cursor/hooks/enforce-cheap-agent-model.sh
```

## Adding New Hooks

1. Add the script to `.cursor/hooks/<name>.sh` and `chmod +x` it.
2. Register in `.cursor/hooks.json` under the appropriate event key.
3. Document it in this README.
4. Test it manually (see testing pattern above).
5. Set `failClosed: true` for any security or cost-enforcement hook.

## hook.json Schema Reference

```json
{
  "version": 1,
  "hooks": {
    "<eventName>": [
      {
        "command": ".cursor/hooks/<name>.sh",
        "failClosed": true,
        "matcher": "optional regex",
        "timeout": 10
      }
    ]
  }
}
```

Supported events: `subagentStart`, `subagentStop`, `beforeShellExecution`, `afterShellExecution`, `preToolUse`, `postToolUse`, `sessionStart`, `sessionEnd`, `afterFileEdit`, `beforeMCPExecution`, `afterMCPExecution`.
