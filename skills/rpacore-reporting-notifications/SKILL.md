---
name: rpacore-reporting-notifications
description: Generate and deliver RPA Core reports and notifications. Use for report renderers, artifact publication, notifier construction, delivery failures, and sensitive operator output.
---

# Build reports and notifications

Run the project's `rpacore version` and compare it with the exact supported
version in [`references/compatibility.json`](references/compatibility.json).
Stop on a mismatch or a missing resource; do not guess compatibility.

Read the reporting sections of the [API reference](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/api.md) and
[security guidance](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/security.md) for formats and transports.

1. Use generate_report for the completed Transaction; render explicitly with
   render_json, render_text, or render_html.
2. Publish files atomically when readers must not see partial output, then
   record meaningful outputs as artifacts. Define how replay verifies that a
   published output belongs to the same operation.
3. Use build_notifiers(config, credentials), then dispatch explicitly as an
   external side effect. Keep delivery failure distinct from transaction outcome.
   Do not assume a durable outbox or retry API absent from the selected version.
4. Test rendering without network access and transports against controlled
   fakes or disposable endpoints.

Do not infer or rewrite captured outcome fields. Minimize sensitive data
before it enters state, arguments, metadata, artifacts, exceptions, reports,
or notification payloads. Never report delivery success after transport failure.
