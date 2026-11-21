# Actor-owned PostgreSQL connection/transaction gate

Status: source contract implemented; live PostgreSQL wire execution is not yet implemented.

## Safety properties

The driver owns one authoritative `DbConnectionState` per physical connection.
Callers never gain authority by constructing or retaining their own state object.

Every operation must match:

- exact physical connection identifier;
- exact actor identity;
- exact actor incarnation/generation;
- exact monotone pool lease generation;
- exact tenant PostgreSQL role;
- a phase that admits the requested transition.

A connection cannot be released while a transaction is active. Actor abort moves
an active transaction to `rollback_required`; that connection remains
quarantined until the transport has completed ROLLBACK and the driver explicitly
acknowledges a clean idle protocol state.

A released connection may be reassigned only with a strictly larger lease
generation. This prevents an old actor ticket from becoming valid again when a
pool recycles the same physical connection.

## Transport acknowledgement boundary

`acknowledge_commit_checked` is not a SQL command. The future wire adapter may
call it only after PostgreSQL has confirmed successful COMMIT.

`acknowledge_abort_rollback_checked` is likewise allowed only after ROLLBACK
has completed and the protocol is known to be idle. EOF, cancellation,
desynchronization, timeout with unknown outcome, or any unexpected backend
message must destroy/quarantine the connection rather than manufacture an
acknowledgement.

The same rule applies to pool release: a live adapter must reset tenant role and
other session state, verify the reset, or destroy the connection.

## Planned NIO binding

The Java/Graal runtime has an active stacked NIO client contract exposing
`network.connect_async(host, port)` and affine `NioTcpConnection` async
read/write/close operations. That stack is not present in this repository's
current pinned compiler (`SOURCE_REF`), so this PR deliberately does not invent
a socket API or claim native driver execution.

Once the required runtime stack is available at a reviewed compiler pin, the
PostgreSQL protocol adapter should:

1. acquire a driver-owned connection state before socket/session admission;
2. perform startup/authentication with bounded frame sizes;
3. bind typed `DbValue` parameters separately from SQL text;
4. map PostgreSQL ErrorResponse SQLSTATE into typed execution errors;
5. deliver cancellation through a separately authorized cancellation path;
6. keep transaction state actor-local and generation-fenced;
7. require explicit COMMIT/ROLLBACK protocol completion before state transition;
8. apply the tenant role and rely on database RLS as a second enforcement layer;
9. reset and verify session state before pool reuse;
10. destroy the connection on unknown protocol or transaction state.

## Evidence classes

The pure guest tests in `tests/plans.ores` exercise the ownership/fencing state
machine when the pinned compiler can run them. They are not network evidence.

The PostgreSQL 17 Bash fixtures exercise real PostgreSQL behavior, including RLS,
typed coercion, SQLSTATE and cancellation. They are not Oreslang driver
evidence.

Release requires both of those plus a real Oreslang wire adapter exercising the
same cases end to end.
