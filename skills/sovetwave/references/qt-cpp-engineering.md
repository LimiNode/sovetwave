# Qt C++ engineering

Read this reference only when the C or C++ scope actually uses Qt. Establish the
Qt major and minor version, enabled modules, build system, and project profile
before proposing APIs or framework-specific policy. Prefer the project's pinned
documentation; when an optional Qt documentation tool is available, use it
without adding or distributing a local MCP configuration.

## Separate application and framework rules

An application, an internal library, a plugin, and a compatibility-stable Qt
framework have different obligations. Export macros, private-header conventions,
d-pointers, symbol visibility, QML versioning, and binary-compatibility review
belong only where the repository establishes the corresponding public boundary.
Do not infer framework mode from `QObject`, a directory name, or one export
macro. Confirm it from targets, public headers, packaging, consumers, and release
policy.

For a public Qt library, inspect changes to exported classes, layouts, virtual
functions, inline code, enums, metatypes, templates, compiler options, and
ownership across the boundary. For application-private code, do not add ABI
machinery merely because a framework would need it.

## Respect the meta-object and ownership contracts

Qt strongly recommends `Q_OBJECT` in every `QObject` subclass, but its absence
alone does not establish a correctness defect in the shown class. Establish
whether the class declares signals, properties, invokable methods, or other
features that require its own generated meta-object. Check project policy and
uses such as `qobject_cast`, generated code, QML, and direct meta-object access
before accepting the omission or changing the class. Conversely, do not remove
`Q_OBJECT` merely because no signal declaration is visible locally.

For every `QObject`, establish its lifecycle from a parent, an owning C++ type,
an explicit deletion path, or an external owner. A raw pointer may be a valid
non-owning observation; the type alone does not prove a leak. Check that parent
and child thread affinity is compatible and that destruction happens through an
event loop when `deleteLater()` is used. Do not prescribe `deleteLater()` where
no running event loop can deliver it.

Use guarded observations such as `QPointer` when an independently owned
`QObject` may disappear before a callback, but do not replace clear ownership
with guards as a reflex.

## Check thread affinity and asynchronous boundaries

Treat a `QObject` as belonging to its affinity thread unless the documented API
is thread-safe. Inspect where an object is created, moved, invoked, and destroyed.
For each signal/slot boundary, establish sender context, receiver affinity,
connection type, argument lifetime, and shutdown behaviour. A direct connection
runs in the emitting thread; a queued connection defers work to the receiver's
event loop. Do not call either universally correct.

Do not mutate GUI objects outside the GUI thread. Call `QAbstractItemModel` API
only from the model object's affinity thread unless a documented API provides a
stronger guarantee. A model connected to a view normally belongs to the GUI
thread; background workers may prepare data and queue the corresponding model
update to that thread. A model that legitimately lives and is used in a worker
thread is not defective merely because the thread is not the GUI thread.

For models, verify structural begin/end pairs on every path, index ranges,
`setData()` and `dataChanged` consistency, and whether the changed-role list is
intentionally broad or precise. An empty roles list means all roles changed; it
is not automatically a protocol violation.

## Account for implicit sharing and containers

Qt implicit sharing can turn an apparently read-only operation into a detach
when a non-const API is selected. Inspect constness, iterator type, range-for
expansion, and `operator[]` use before reporting allocation or copy cost. Confirm
that the object is actually shared or that the path is performance-relevant
before elevating the issue.

Apply ordinary C++ lifetime and invalidation rules to Qt containers, views,
callbacks, and implicitly shared data. Qt ownership conventions do not repair a
dangling C++ reference.

## Generate and review Qt-facing CMake carefully

Read the project's `cmake_minimum_required`, requested Qt version, targets,
policies, and existing style before changing CMake. Verify the exact command and
option against documentation for that Qt version; do not invent a newer command,
policy, or argument and then raise the minimum version to justify it.

Use target-based dependencies and choose `PRIVATE`, `PUBLIC`, or `INTERFACE`
from the actual consumer contract. Let Qt's supported CMake integration manage
generated meta-object, UI, resource, and QML artefacts; do not list generated
outputs manually. Preserve an established qmake build only when it remains an
explicit project requirement; do not mix qmake syntax into CMake.

After a build-system change, perform a clean configure and the narrowest build
and test that exercise the affected target. A successful configure does not
prove that plugins, QML imports, resources, or deployment artefacts work at
runtime.
