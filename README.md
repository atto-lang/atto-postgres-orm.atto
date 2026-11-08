# atto-postgres-orm.atto

PostgreSQL object-relational mapping and database integration implemented in AttoLang.

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

AttoLang is the public name; preserve existing Oreslang/.ores compatibility and use canonical .atto for new portable library source. This README defines scope, not feature readiness.

**Acceptance:** name exact source SHA/tree, runtime/toolchain, positive and negative checks and execution receipt before claiming support. Host-only tests and empty CI steps do not prove guest execution.
