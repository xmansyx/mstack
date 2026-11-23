# Example project conventions

This is a format, not a rulebook. Copy it into your repository (for example as
`docs/conventions.md`, linked from `AGENTS.md`), replace the rows with rules your
codebase actually follows, and delete the rest. The review lenses read the
sections named below; a project without this file is reviewed against its own
instructions and the nearest existing flow.

Each review violation needs the diff line and verified prior art or an explicit
requirement. Absence from this file is not approval.

## Implementation entry points

Where a reviewer or implementer should look first for each responsibility. Paths
are leads to the current code, re-checked before use, not a blanket endorsement of
everything in those files.

| Responsibility | Where to look | Decision to carry into implementation |
|---|---|---|
| Admin endpoints | `src/controllers/AdminController.ts`, `src/routes/admin.ts` | Extend the domain's existing controller and service; keep its authentication, permission and error wrappers |
| External API responses | `src/integrations/<vendor>/client.ts` | Parse responses from `unknown` with the existing validator; report failures with fixed classifications, never raw bodies or credentials |
| UI buttons, menus and API calls | `src/components/Button.tsx`, `src/lib/api.ts` | Check existing props and helpers before creating another primitive, HTTP client or error parser |

## Money & payments

| Rule | Why | Violation looks like | Canonical |
|---|---|---|---|
| Currency comes from the payment provider or account config; never hardcoded, listed or defaulted | A wrong currency is wrong money | A `['USD','EUR']` array, `currency = 'USD'` | `src/payments/config.ts` |
| No currency fallback; a missing currency is an error the caller handles | A fallback produces a plausible wrong number instead of a visible failure | `currency ?? 'USD'` | — |
| Amounts keep one representation end to end (minor units) | Mixed representations produce 100× errors | `amount / 100` at call sites, float arithmetic on money | `src/payments/money.ts` |

## Data & persistence

| Rule | Why | Violation looks like | Canonical |
|---|---|---|---|
| Every new production query filter and sort has a supporting index | Unindexed queries on large tables time out under load | New query on a large collection with no index or migration | — |
| Changes to already-persisted data ship with a migration and a compatible read path | Existing rows predate the new shape; wholly new, unmerged models need neither | Required field added to an existing model with no transition | — |
| Index drops, migrations and backfills are called out in the PR body | Undeclared index changes break deploys | Silent index change | — |

## Auth & scoping

| Rule | Why | Violation looks like | Canonical |
|---|---|---|---|
| Tenant scoping goes through the central mechanism, never hand-rolled filters | One forgotten filter exposes another tenant's data | `find({ accountId: req.user.accountId })` in a new controller | `src/middleware/tenantScope.ts` |
| New routes declare their permission explicitly | An undeclared route is either open or silently broken | New route with no permission declaration | — |
| Never trust client-supplied account, owner or amount identifiers | Trivially forged | `req.body.accountId` used in a query unchecked | — |

## Infra & services

| Rule | Why | Violation looks like | Canonical |
|---|---|---|---|
| Shared clients (cache, queue, mail) go through their wrapper | The wrapper hides environment differences and is what tests mock | `new Redis(...)` where the wrapper would do | `src/lib/cache.ts` |
| Bulk and scheduled sends go through the existing send engine | Ad-hoc loops bypass retries, dedup, rate limits and status tracking | `for (const c of contacts) await send(c)` in a controller | — |
| A status has one source of truth | A parallel status field drifts from the real lifecycle | New status field beside an existing one | — |

## Types & style

| Rule | Why | Violation looks like |
|---|---|---|
| Model real types; validate uncertain external values from `unknown` | Static assertions cannot validate runtime data | `as any`, `as unknown as T` |
| No lint or type suppressions | Fix the code, don't suppress the signal | `eslint-disable`, `@ts-ignore` |
| Types shared by more than one app live in the shared package | A redeclared type diverges at the boundary | Local interface mirroring an exported one |
| Delete the old path; no compatibility shims or dead flags without approval | Both paths alive means neither is understood | Old function kept "for now" |

## Process

| Rule | Why | Violation looks like |
|---|---|---|
| Stacked PRs base on the previous PR's head | A stacked PR based on trunk re-includes its siblings' diff | Mid-stack PR based on trunk |
| One idea per PR | Two ideas cannot be reviewed or reverted separately | Title joins unrelated changes with "and" |
| The PR description matches the diff | A description claiming absent work gets wrong code approved | Body describes behavior not in the diff |
| No secrets, tokens or full request bodies in logs | Logs are widely readable and long-lived | `logger.info(req.body)` |
| Test fixtures never hardcode absolute dates | Dates fall into the past and turn CI red for unrelated reasons | `new Date('2026-08-01')` in a fixture |

## Adding a rule

Add one when a review finds a pattern the team follows everywhere but this file
does not list. Require three existing call sites proving it is a real convention,
a one-line why (what breaks without it), and a canonical path a future reviewer
can cite. Mark a rule you have not re-verified with ⚠ and confirm it before
enforcing it.
