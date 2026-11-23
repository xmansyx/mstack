# Lens: data, migrations and contracts

What happens to existing data and to every consumer when this ships, in the order
it will actually deploy? Project conventions to read, when the project has them:
data and persistence, and infra and services.

| Area | Look for |
|---|---|
| Persisted shape | A changed field on existing documents without a migration, backfill or a reader that tolerates both shapes. Wholly new, unmerged data needs none |
| Indexes | New production query filters and sorts have an index; index creation on large collections follows the production process; dropped indexes are called out |
| Migrations | Idempotent, resumable after a crash, safe to run twice, sized for production data; whether down() is possible or destroys data |
| Deploy order | A consumer that ships before its producer, a reader before the writer, a portal before the server endpoint it calls; flags and env vars that must exist first |
| Contracts | API, webhook, event, queue payload and shared-package changes: list every consumer in every repository at its pinned revision; a removed or renamed field is breaking until each consumer is checked |
| State | A parallel status field beside an existing lifecycle; transitions the old code still writes; states nothing can reach or leave |
| Cross-repository | A shared package ships with or before its consumers; a contract duplicated by hand on both sides of a boundary is checked on both sides. Resolve sibling repositories through `stack-resolution.md`, never by directory name |

When the consumer search is broad, search every repository that could consume the
changed shape at its pinned revision before calling a change internal.

Every candidate needs a failure scenario: the deploy or data state, the action, and
the wrong result.
