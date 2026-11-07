# Bounded reproduction recipe

This is a record of the setup used for the already completed local
experiment. It is not an instruction to perform another model or network
call. Any rerun requires separate authorization.

## Environment

- Windows 11 Pro `10.0.26100`
- PowerShell `5.1.26100.8875`
- Python `3.11.9`
- Claude Code `2.1.120`
- local provider selected through `ANTHROPIC_BASE_URL` on port `8080`
- project settings only; `Bash` was the sole allowed tool and permission mode
  was `dontAsk`

The provider host and credential value are intentionally not recorded here.

## Disposable fixture

Create a temporary project outside the repository and a hook that reads JSON
from stdin, records only the `tool_name`, `tool_input.command`, and
`tool_use_id`, then returns:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "bounded evidence fixture"
  }
}
```

Configure a project-level `PreToolUse` matcher for `Bash`, use a forward-slash
portable command path, and set the matrix timeout to one second. Ask the host
for exactly one harmless marker command in each case. Preserve the marker
existence result and the structured hook lifecycle events.

## Expected interpretation

- Explicit JSON `deny` must produce a hook event and no marker.
- Exit `1`, malformed stdout, and timeout must be recorded separately; on the
  tested `2.1.120` setup they allowed the marker command.
- An absent-hook control and user/repository precedence are separate tests and
  were not run for this record.

Do not infer a fail-closed adapter from a blocked call caused by a broken hook
path or by an exit code that the host interprets as an explicit denial.
