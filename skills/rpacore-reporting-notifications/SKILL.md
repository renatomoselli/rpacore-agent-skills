---
name: rpacore-reporting-notifications
description: Generate and deliver RPA Core reports and notifications safely. Use with generate_report, renderers, artifacts, build_notifiers, dispatch, report versioning, or sensitive operator output.
---

# Build reports and notifications

Before changing code, run `rpacore version` and confirm it satisfies the Core
range in the repository's [`manifest.toml`](../../manifest.toml). Stop on a
mismatch.

Read the reporting/notification section of the public
[API reference](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/api.md)
and
[security guidance](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/security.md)
for exact formats and transport behavior.

## Workflow

1. Create terminal truth with `generate_report(transaction)` for the completed
   `Transaction`; render explicitly with `render_json`, `render_text`, or
   `render_html`.
2. Publish files atomically when readers must not observe partial output, then
   record meaningful outputs as artifacts.
3. Use `build_notifiers(config, credentials)` to construct the notifier list,
   then call `dispatch(notifiers, report)` as an explicit external side effect
   with bounded failure behavior.
4. Test rendering without network access and transports against controlled
   fakes or disposable endpoints.

Do not infer or rewrite captured report outcome fields. Minimize sensitive data
before it enters transaction state, arguments, metadata, artifacts, exceptions,
reports, or notification payloads. Never report delivery success after a
transport failure.
