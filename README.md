> **AI agent instructions (organization-wide):** Before working on code, issues, or pull requests, read and follow the [organization `AGENTS.md`](https://github.com/atto-lang/.github/blob/main/AGENTS.md), including its **merge-first stealth-development policy**. Honor any repository-local `AGENTS.md`, explicit holds, and GitHub-enforced rules.

# atto-postgres-orm.atto

PostgreSQL object-relational mapping and database integration implemented in AttoLang.

## Naming migration and language authority

This repository is maintained at [atto-lang/atto-postgres-orm.atto](https://github.com/atto-lang/atto-postgres-orm.atto); use `https://github.com/atto-lang/atto-postgres-orm.atto.git` for Git remotes and canonical `.atto` source examples. The normative language contract is [atto-spec](https://github.com/atto-lang/atto-spec), with executable guest evidence tracked by [atto-platform-conformance](https://github.com/atto-lang/atto-platform-conformance). Follow current ownership, borrowing, effects, actor, and syntax rules there; do not infer implemented features from a README or unexecuted CI.

## Responsibilities

PostgreSQL models, query/mapping behavior, and database adapters written in AttoLang.

## Design guidelines

- Keep application-facing contracts separate from hosted Atto services.
- Explicitly specify error, cancellation, concurrency, and resource-lifecycle behavior where applicable.
- Document supported compiler backends, host restrictions, wire formats, and compatibility constraints.

## Development and verification

Use the source tree and CI for verified build/test commands. Tests should cover positive cases, invalid inputs, lifecycle behavior, and cross-backend interoperability where relevant.

## Status

This README describes the project's intended role. It does not imply that the listed APIs or platforms are already implemented or supported.

## Related

- [AttoLang](https://github.com/atto-lang)
- [Language specification](https://github.com/atto-lang/atto-spec)
- [Platform conformance](https://github.com/atto-lang/atto-platform-conformance)

## Repository ownership and contribution routing

**Belongs here:** AttoLang PostgreSQL schema/model mappings, query composition, typed result decoding and Postgres driver adapters.

**Belongs elsewhere:** Database-neutral APIs in atto-db; raw SQL runtime host integration in backend repos; hosted Postgres operations in atto-co.

**Security and portability boundary:** Use parameterized queries, transactional error/rollback tests, bounded result handling and schema migration tests; no inline secrets.

AttoLang is the canonical project name; new source, examples and documentation use `.atto` and the `atto-lang` repository organization. This README defines scope, not feature readiness.

**Acceptance:** name exact source SHA/tree, runtime/toolchain, positive and negative checks and execution receipt before claiming support. Host-only tests and empty CI steps do not prove guest execution.

## Legacy provenance and transfer verification

The historical predecessor, `ores-truffle-oreslang/postgres-orm.ores`, is archived; the current `atto-lang/atto-postgres-orm.atto` has a separate numeric GitHub repository ID. Preserve working legacy `.ores` fixtures and package/CLI/API aliases until canonical `.atto` replacements are verified. Schema-first ORM, typed CRUD, reviewed migration previews and database contract tests belong here, not production database operator privileges or commercial managed database administration.

[atto-lang](https://github.com/atto-lang) owns language and portable tooling; [atto-co](https://github.com/atto-co) separately governs managed infrastructure, tenant hosting, identity and billing. Any future original-ID transfer or commercial carve-out requires separate owner authorization and independent security review. Inventory exact SHA/tree, numeric ID, access, protections, PRs, releases, packages, runners, secrets, deploy keys, apps, webhooks, Pages, consumers and rollback ownership; verify identity and retest after an authorized transfer. Never mirror private source without authorization. Zero-step jobs are NOT_EXECUTED; host/static checks are not compiled guest evidence, database safety proof or actor parity.
