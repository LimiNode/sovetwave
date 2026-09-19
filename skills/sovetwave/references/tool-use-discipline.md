# Tool-use discipline

Load this reference when the task will invoke shell commands, repository or
editor tools, automation, CLI debugging, or MCP/custom tools. It is a routing
and verification contract, not a new executor, wrapper, or tool taxonomy. For
an ordinary answer that needs no tool, do not load it.

## Select the narrowest available tool

1. Prefer the most specific structured tool whose contract directly owns the
   requested operation. A purpose-built repository tool outranks a generic
   command runner when it provides the operation and its validation.
2. Otherwise prefer a typed host-native tool when the host exposes the needed
   operation with structured arguments and, when relevant, explicit
   working-directory and status fields.
3. Use a direct shell command for a simple operation when no more specific
   tool exists. Do not prescribe a structured API that the current host does
   not provide.

A tool's schema is part of its contract. Supply paths, options, and modes in
the typed fields when they exist; validate required fields and allowed values
before execution. If the schema is unclear, inspect its help or description
instead of guessing from a similarly named command.

## Establish the actual interpreter

Identify the shell or interpreter that will parse the command before writing
quoting or escaping. Bash, PowerShell, `cmd.exe`, Python, and a tool's own
expression language have different rules; do not transfer quoting by analogy.
Use the host's `workdir` field when it is available. Otherwise make the
working directory explicit and verify it at the boundary.

Minimise parser layers. A direct command is preferable to a shell invoking a
second shell that invokes a script with another expression parser. Every layer
must have a reason, and its quoting must be checked for the actual target
interpreter. A path containing spaces is a path test, not permission to add a
quoting circus.

## Make edits through an editing interface

For a non-trivial edit, use a patch or editor tool with structured file
boundaries when the host provides one. Keep large payloads and multiline text
out of command-line quoting when an editing interface is available. Use a
shell for a direct, bounded transformation only when its input, output, and
failure behaviour are clear.

Before a destructive or broad command, establish the exact target and scope.
Do not widen a command merely because the first path or pattern was
inconvenient.

## Observe a bounded result

Start with the smallest observation that can distinguish the next decision:
status and metadata, a bounded excerpt, or a focused diagnostic. Inspect
`--help` or a local error before expanding the search. Do not dump a large
file, recursive tree, or unbounded log when a bounded query is sufficient.

Keep three signals separate:

- process or tool status: exit code, structured status, timeout, or transport
  error;
- textual output: stdout, stderr, or returned message;
- semantic result: whether the requested repository or system property now
  holds.

Absence of textual output is not itself a failure signal. A successful command
may be intentionally silent. Interpret exit codes and structured statuses
according to the documented contract of the particular tool: a non-zero
status may represent a negative predicate result, a partial result, or an
execution failure. Do not infer success or failure from stdout or stderr alone.
Claim success only from the signal that proves the requested property.

## Classify failure before retrying

After a tool failure, classify the boundary before making another call:

- malformed arguments or unsupported syntax;
- wrong path, working directory, interpreter, or environment;
- permission, authentication, or tool-availability failure;
- timeout or unknown side effect;
- transient transport or service failure;
- command completed but the semantic condition failed.

Change the relevant input, inspect the state, or stop according to that
classification. Never repeat an unchanged failed call unless the evidence
identifies a transient condition. After a timeout, inspect for partial effects
and consider idempotency before retrying. A retry is not a repair for an
unknown command contract.

For an unfamiliar CLI, inspect its `--help`, subcommand help, or repository
documentation before trying syntax variants. For a known local fix with an
explicit path, command, and success signal, act directly rather than opening a
generic inquiry loop.

The informal "quote budget" is a useful warning sign: as nested interpreters,
escaping layers, and embedded multiline payloads accumulate, stop and look for
a typed argument or editing tool. It is a heuristic for choosing a clearer
call, not a score, gate, or runtime metric.
