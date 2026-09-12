# Evaluating the workflows

Executable reference consumers live in tests/consumer_scenarios.py and run
through scripts/verify_consumer.py. They cover scaffold execution and generated
tests, durable two-step recovery after publication, conflicting output,
definition mismatch, and distinct business/system outcomes.

For an actual authoring evaluation, give a fresh agent the relevant skill,
the manifest, the request and raw fixtures. Withhold the reference solution.
Use a disposable workspace and controlled local clients. Record the request,
skill/manifest hashes, harness/model identity when available, generated
artifact hashes, commands, results, and remaining limitations separately from
the reference-consumer receipt. No case authorizes live services or publication.

| Request / fixture | Relevant workflow | Observable assessment |
| --- | --- | --- |
| “Design daily supplier-report processing”; one input sample and business rules | Automation development | Explicit unit of work, execution-mode rationale, JSON-safe recovery inputs, business/technical failures, and unresolved rules |
| “Make this existing CSV total script recoverable”; original script and CSV | Automation development + durability | Original output parity, controlled failure handling, new-process recovery across the external-effect/checkpoint gap, and stated input/concurrency assumptions |
| “Upgrade this existing Core project”; selected source/target package artifacts and copied databases | Project setup + durability | Actual source/target compatibility result, preserved definition identity where appropriate, rejected unidentified/incompatible work, and rollback evidence |
| “Review this single regression” versus “Review this automation broadly” | Testing and review | Narrow request stays focused; broad request includes substantiated defects and useful bounded opportunities with evidence and value tests |
| “Diagnose this interrupted job”; synthetic records containing secret canaries | Diagnostics | Answer distinguishes durable truth from uncertain external effects; shared output excludes the canaries and unnecessary payloads |
| “Retry this submission after a timeout”; fake client with no idempotency or acceptance lookup | Durability + queue processing | Explicit uncertainty/reconciliation limit instead of an unsupported automatic retry or success claim |

Assess behavior and generated artifacts; matching wording or headings is not
success. A case may correctly identify an unsupported recovery or migration
path. Reference consumer tests on the target version do not validate every
historical migration, and a single local agent run does not establish broad
model reliability or installation-channel support.
