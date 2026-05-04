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
4. **Soft policy (Rule #5):** `gpt-5.5-medium` and `claude-4.6-sonnet-medium-thinking` emit a **warning** when the prompt bundle lacks a case-insensitive `# justification:` line; dispatch still proceeds (`permission: allow` + `user_message`).

If any hard check fails, returns `{"permission":"deny", "user_message": "<remediation>"}` and blocks the dispatch.

**Allow-list:**

| Model slug | Size | Est. cost |
|-----------|------|-----------|
| `composer-1.5` | XS | ~$0.10 |
| `composer-2-fast` | S | ~$0.40 |
| `gpt-5.5-medium` | M | ~$1.00 |
| `claude-4.6-sonnet-medium-thinking` | L | ~$3.00 |

**Blocked:** Any model containing "opus" (XL — orchestrator only).

**Doctrine:** `.cursor/rules/cheap-agent-fleet.mdc` Rule #2 + Rule #5
**Canonical reference:** `docs/PR_TSHIRT_SIZING.md`

#### Testing locally

```bash
# Should deny — Opus model
echo '{"model":"claude-4.5-opus-high-thinking"}' | bash .cursor/hooks/enforce-cheap-agent-model.sh

# Should deny — missing model
echo '{"task":"do something"}' | bash .cursor/hooks/enforce-cheap-agent-model.sh

# Should allow — valid composer model
echo '{"model":"composer-1.5"}' | bash .cursor/hooks/enforce-cheap-agent-model.sh

# Should allow with WARNING — non-composer without justification
echo '{"model":"gpt-5.5-medium","prompt":"ping"}' | bash .cursor/hooks/enforce-cheap-agent-model.sh

# Should allow without warning — justification present
echo '{"model":"gpt-5.5-medium","prompt":"# justification: security-sensitive diff review"}' | bash .cursor/hooks/enforce-cheap-agent-model.sh
```

### `enforce-worktree.sh` — subagentStart

**Event:** `subagentStart`
**failClosed:** `true`

Ensures subagent sessions are not launched from the canonical main checkout at `/Users/paperworklabs/development/paperwork` (or `$HOME/development/paperwork`). Paths containing `paperwork-worktrees/` are always allowed. When `cwd` is absent from the payload, the hook **allows** but returns a NOTICE `user_message` so the gap is visible (deliberate trade-off — see script header).

**Doctrine:** `.cursor/rules/cheap-agent-fleet.mdc` (worktree discipline + procedural memory references)

#### Testing locally

```bash
# Should deny — main checkout path
echo '{"cwd":"/Users/paperworklabs/development/paperwork"}' | bash .cursor/hooks/enforce-worktree.sh

# Should allow — worktree path
echo '{"cwd":"/Users/paperworklabs/development/paperwork-worktrees/sample-branch"}' | bash .cursor/hooks/enforce-worktree.sh

# Should allow + NOTICE — missing cwd
echo '{"model":"composer-1.5"}' | bash .cursor/hooks/enforce-worktree.sh

# Should deny — invalid JSON (parser surface)
echo 'not-json' | bash .cursor/hooks/enforce-worktree.sh
```

### `enforce-rules-attachment.sh` — subagentStart

**Event:** `subagentStart`
**failClosed:** `true`

Requires pinned rules on every cheap-agent dispatch. Pass if **either**:

- A non-empty `rules` array is present on any of `.rules`, `.input.rules`, `.params.rules`, `.task.rules`, `.taskParams.rules`, **or**
- Any prompt field (`.prompt`, `.input.prompt`, `.params.prompt`, `.task.prompt`, `.taskParams.prompt`) contains a line matching `# rules:` (case-insensitive) **or** a `## Pinned rules` markdown heading.

**Doctrine:** `.cursor/rules/cheap-agent-fleet.mdc` Rule #2

#### Testing locally

```bash
# Should deny — no rules array or markers
echo '{"model":"composer-1.5","prompt":"do work"}' | bash .cursor/hooks/enforce-rules-attachment.sh

# Should allow — rules array present
echo '{"model":"composer-1.5","rules":[".cursor/rules/cheap-agent-fleet.mdc"]}' | bash .cursor/hooks/enforce-rules-attachment.sh

# Should allow — markdown pinned section
jq -n --arg p $'## Pinned rules\n- cheap-agent-fleet.mdc' '{model:"composer-1.5",prompt:$p}' \
  | bash .cursor/hooks/enforce-rules-attachment.sh

# Should allow — # rules: line
echo '{"model":"composer-1.5","task":{"prompt":"# rules: cheap-agent-fleet.mdc"}}' | bash .cursor/hooks/enforce-rules-attachment.sh

# Should deny — invalid JSON
printf '{' | bash .cursor/hooks/enforce-rules-attachment.sh
```

### `enforce-no-direct-main-push.sh` — beforeShellExecution

**Event:** `beforeShellExecution`
**failClosed:** `true`

Blocks shell commands that attempt to push directly to `main` / `master` on `origin` (including force / delete ref forms enumerated in the script). Applies to **all** shell executions — not just subagents — matching `.cursor/rules/git-workflow.mdc`.

**Doctrine:** `.cursor/rules/git-workflow.mdc`

#### Testing locally

```bash
# Should deny — direct push to main
echo '{"command":"git push origin main"}' | bash .cursor/hooks/enforce-no-direct-main-push.sh

# Should allow — feature branch
echo '{"command":"git push -u origin feat/demo"}' | bash .cursor/hooks/enforce-no-direct-main-push.sh

# Should allow — push current HEAD without naming main
echo '{"command":"git push -u origin HEAD"}' | bash .cursor/hooks/enforce-no-direct-main-push.sh

# Should deny — delete main ref
echo '{"command":"git push origin :main"}' | bash .cursor/hooks/enforce-no-direct-main-push.sh

# Should deny — invalid JSON
echo 'nope' | bash .cursor/hooks/enforce-no-direct-main-push.sh
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
