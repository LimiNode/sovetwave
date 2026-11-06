# Claude `PreToolUse` evidence record

Status: research-only evidence preservation. This directory does not contain a
production adapter, a command classifier, or a host-enforcement implementation.

The record preserves a bounded local observation for Claude Code `2.1.120`,
the `Bash` route, and a local provider. It must not be read as evidence for
universal tool coverage, fail-closed hook failure handling, or user-level
policy precedence.

## Scope and evidence classes

The original local runs happened before this record was created. Their source
bundles were checked by SHA-256 on 2026-11-06 and their JSON/Markdown contents
were inspected. The raw Claude stream was not retained in those bundles.

| Claim | Evidence class | Boundary |
|---|---|---|
| Claude Code exposes `PreToolUse` for `Bash` in the recorded setup | `artifact-verified` plus `locally observed` | one installed binary and one project settings fixture |
| Explicit JSON `permissionDecision: "deny"` preceded the attempted Bash side effect | `agent-reported` / `locally observed`; hook record is `artifact-verified` | complete tool-result stream is not sealed in this repository |
| Hook exit `1`, malformed stdout, and timeout allowed the marker command in the matrix | `agent-reported` / `locally observed`; matrix summary is `artifact-verified` | no claim beyond Claude Code `2.1.120` and this configuration |
| Hook failure is fail-closed on all routes | `not_assessable` and not claimed |
| Repository-local settings cannot weaken user-level policy | `not_assessable` |

`documented` claims are limited to the published Claude hooks contract. They
are not substituted for the local execution observation.

## Source bundles

The source bundles remain outside the repository. Their files and hashes are
listed in `source-integrity.json`; no API key, user prompt, home-directory
path, or full local filesystem path is copied here. The preserved reports are
the source of the bounded observations, not new executions.

## Environment and trust scope

- OS: Windows 11 Pro `10.0.26100`, PowerShell `5.1.26100.8875`.
- Python: `3.11.9`.
- Claude Code: `2.1.120`; binary SHA-256 is recorded in
  `evidence-summary.json`.
- Provider transport: `ANTHROPIC_BASE_URL` pointed to a local LAN endpoint on
  port `8080`; the host address and local GGUF path are redacted here.
- Authentication: the credential value was not recorded. No secret is part of
  this evidence record.
- Settings: `--setting-sources project`, an explicit disposable settings file,
  `--permission-mode dontAsk`, and only the `Bash` tool allowed.
- Hook trust: project settings were loaded for the disposable fixture; the
  record does not establish precedence over user-level settings.

## Hook configuration shape

The disposable fixture used the following sanitized shape. `<fixture>` is a
placeholder, not a path to be resolved from this repository:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python <fixture>/deny_hook.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

The failure matrix used the same shape with `timeout: 1` and a fixture hook
that selected explicit deny, exit `1`, malformed stdout, or a four-second
sleep from the attempted marker command. These cases remain separate; an
absent-hook control was not run.

## Reproduction boundary

`reproduction.md` records the minimal disposable setup and the expected
observations. It is documentation only. Running it would be a new local model
and network experiment and requires a separate explicit authorization.

The next decision remains whether a version-pinned Claude-specific adapter can
be designed. This record does not authorize that implementation.
