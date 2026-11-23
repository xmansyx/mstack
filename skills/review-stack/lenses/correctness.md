# Lens: correctness and concurrency

Does the changed code do what it claims, under every input and interleaving it
will meet? Project conventions to read, when the project has them: infra and
services, and any concurrency or error-handling rules.

| Area | Look for |
|---|---|
| Logic | Off-by-one, inverted conditions, wrong operator (`<` vs `<=`), unreachable branches, a case the switch forgets |
| Null and absence | Optional chains hiding real absence, defaults masking a missing value, non-null assertions |
| Async | Missing `await`, unhandled rejections, `Promise.all` over unbounded user input, work after a response is sent |
| Races | Read-modify-write on shared documents, check-then-act without a conditional update, two writers for one key, ordering assumptions between jobs |
| Idempotency | Webhooks, payment callbacks, queue consumers and retried jobs survive being delivered twice and converge after a crash mid-way |
| Errors | Swallowed catches, an error returned as success, partial writes without rollback or a resumable path |
| Loops and queries | N+1 queries, missing pagination, a full collection scan on a request path |
| Dates | Timezone handling, DST, end-of-day boundaries; clock-dependent tests that do not control time |
| Untested failure paths | The failure scenario you found has no test that would catch it; name that scenario, not "more tests" |

Every candidate needs a failure scenario: concrete input or sequence → wrong result.
For a race, name the two actors and the interleaving. If you cannot write one, drop it.
