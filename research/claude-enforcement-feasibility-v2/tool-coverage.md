# Claude route and tool coverage

`PreToolUse` is a hook event, not a proof that every side effect in Claude
Code passes through it. Coverage is therefore recorded per route and per
evidence class.

The official hooks reference documents matching built-in tools and MCP tool
names. It also documents cases where no tool call is emitted; such a path is
outside `PreToolUse`. The table below deliberately avoids turning those
documented names into universal enforcement claims.

| Route | Current documentation | Preserved local evidence | Coverage status | Required proof |
|---|---|---|---|---|
| `Bash` | `documented`: matchable `PreToolUse` route | `artifact-verified` summary plus `locally-observed` explicit deny and failure matrix | One route, one version, one fixture | Raw event stream, deny-before-marker, and failure controls on the pinned binary |
| `Read` | `documented`: built-in tool can be matched by hook configuration | `not-assessable`: not run | Unknown | Read-only fixture with request/result correlation and malformed/timeout controls |
| `Write` | `documented`: built-in tool can be matched by hook configuration | `not-assessable`: not run | Unknown | Disposable file fixture; prove deny leaves file unchanged |
| `Edit` | `documented`: built-in tool can be matched by hook configuration | `not-assessable`: not run | Unknown | Disposable file fixture; prove deny leaves exact bytes unchanged |
| MCP tools | `documented`: MCP tool names are matchable when they enter the host tool path | `not-assessable`: not run | Unknown and server-dependent | One local disposable MCP server, one side-effecting method, and raw host/server correlation |
| `PreToolUse` failure path | `documented` current failure policy is version-dependent | `locally-observed` matrix for exit 1, malformed output, timeout on Bash | Not proven fail-closed | Pin a version that supports `onFailure: "block"`; test all failure modes |
| `EndConversation` and other non-tool actions | `documented` exclusions/non-tool paths exist | `not-assessable` | Outside hook coverage | Identify whether any side effect can occur on the path; use an external boundary if yes |
| `@`-style file/context mentions | `documented` can avoid a tool invocation in some cases | `not-assessable` | Potential bypass of a tool-only guard | Treat as no-hook path and verify that no protected side effect is available there |
| Child commands spawned by `Bash` | No independent universal hook claim | `not-assessable` | Inherited from Bash route only if host dispatches Bash | Keep the protected side effect inside the fixture and observe whether the host reports one correlated operation |

## Coverage rule

An adapter must name the route it protects. `Bash` evidence cannot be promoted
to `Write`, `Edit`, MCP, or non-tool coverage. Likewise, an explicit denial on
one tool cannot establish how a hook failure is handled on another tool.

Where the host does not expose a raw request/result correlation, the route is
`not_assessable` for an evidence-grade claim even if the final marker happens
to be absent.

## Known bypass boundary

The documented existence of a path with no `PreToolUse` event is enough to
reject a universal claim; it is not enough to classify the path as exploitable
without an observable side effect. The correct next action is a bounded fixture,
not a larger classifier. If a protected operation can be reached outside the
hook path, mandatory enforcement must move to a trusted external execution
boundary.
