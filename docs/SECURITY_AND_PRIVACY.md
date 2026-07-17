# Security and privacy model

## Current deployment boundary

Agent Anthill is currently a **single-user, local-first development tool**. The default server binds to `127.0.0.1`. It is not a hardened multi-tenant service.

Do not expose it directly to an untrusted network.

## Critical execution warning

The real Python tracing endpoint imports and executes a selected function from the target project in the server process. That code can perform any action allowed to the current operating-system user.

- Trace only code you trust.
- Prefer a disposable virtual environment or sandbox.
- Do not run the server with administrator/root privileges.
- A future subprocess sandbox must replace in-process execution before production claims.

The static AST analyzer does not execute target code.

## Sensitive-data classes

Agent telemetry commonly contains:

- API keys, cookies, environment values, database credentials;
- private prompts, conversation text, memory, and retrieved documents;
- source code and file paths;
- personal, health, financial, or customer data;
- tool arguments/results and side-effect details;
- proprietary model/provider metadata.

## Defaults

- Canonical runtime persistence is `metadata_only` unless explicitly changed.
- The Python adapter stores argument names/counts but not values by default.
- Return values and exception messages require `capture_content=true`.
- OTLP, AG-UI, and LangGraph importers remove prompt/message/state/tool/task/checkpoint/custom/result/error/interrupt values by default while retaining structural counts, field names, lineage, and correlation metadata.
- AG-UI encrypted reasoning values are treated as content and are never persisted by the default import path.
- LangGraph run/thread/task/message/checkpoint IDs, namespaces, node names, state keys, model metadata, and source references may remain visible. Oversized external interrupt IDs are hashed deterministically and their original length is recorded.
- The synthetic exhibit is labelled in manifest, payload, source adapter, and UI.
- The UI escapes event content before inserting it into HTML.
- Private chain-of-thought is outside the schema; use observable plans or reasoning summaries.

The legacy Source X-Ray endpoint still returns its raw trace response to the local browser. Metadata-only controls canonical persistence, not what trusted local code may display in that legacy panel.

Metadata-only does not mean anonymous. Tool names, step/node names, run/thread/task/message/checkpoint IDs, namespaces, JSON field names, patch paths, model/provider names, and source references can still reveal business or personal context. `privacy.contains_sensitive_data=true` is a handling warning; it does not mean the importer encrypted or anonymized the record. Treat ledger files as sensitive telemetry even when content capture is disabled.

## Hash chain limitations

The JSONL SHA-256 chain detects accidental or malicious modification after recording. It does not provide:

- encryption;
- user authentication;
- non-repudiation against an attacker who can rewrite the entire ledger;
- secure timestamping;
- off-host backup.

Production integrity needs authenticated storage, access logs, key management, and signed checkpoints.

## Replay and side effects

Visual replay only rebuilds state and is implemented today. Real rerun is not.

Before real rerun exists, it must enforce:

- sandboxed tools and network policy;
- recorded/stubbed model and tool responses by default;
- explicit approval for external effects;
- idempotency keys;
- side-effect manifests;
- secret redaction and tenant separation;
- checkpoint/code/config version pinning.

A recorded tool event is evidence that an operation happened. It is never authorization to perform the operation again.

Timeline **FORK HERE** is a data operation only: it materializes recorded history and provenance into a new run. It does not replay model calls, tools, network access, or side effects.

## Retention

`privacy.retention_days` is descriptive metadata in the current local store; automatic deletion is not implemented. Operators are responsible for removing run directories according to their policy.

Large encrypted artifacts and automatic field-level redaction are planned. Until then, do not opt into plaintext content for sensitive workloads.

## Hosted deployment requirements

Before a hosted/multi-user deployment, require at minimum:

- authentication and per-project/run authorization;
- TLS and encrypted artifact storage;
- tenant-isolated database/object-store policies;
- request/body limits and ingestion quotas;
- adapter signing or trusted registration;
- audit logging;
- retention enforcement and deletion workflows;
- SSRF/path traversal review;
- subprocess isolation for tracing;
- dependency and container scanning.
