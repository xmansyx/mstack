# The Explainer

The page answers, in about five minutes and without code: what does this stack
build, how does it work, and what about it is risky. The explorer drafts it while
the hunters hunt; the lead adds findings and verdicts.

## Explorer brief

Give the explorer the review pack, the requirements sources, this file and
[report-record.md](report-record.md). It returns a draft record: the resolver's
`prs` and `dependencies`, plus `story`, `sections`, `visuals`, `decisions` and a
one-line `role` per PR. Before returning, it runs
`render_review.py <draft.json> --check --draft` and fixes every problem. It reports
no findings; a defect it notices goes back in one line for the lead to route.

## What to draw

Pick visuals by what the stack changes. A section that prose explains needs none,
and a section the stack does not touch is left out.

| The stack changes | Section | Visual |
|---|---|---|
| Services, repositories, stores, queues or external calls | `architecture` | `graph` of the parts it touches, marked new, changed or untouched; shapes for stores, queues and external systems |
| An interaction between parts | `architecture` | `sequence` of the main path, numbered; a second only for a materially different path |
| What a user sees or does | `journey` | `flow` with before and after lanes; steps the stack adds take `tone: new` |
| Persisted fields, collections or indexes | `data` | `schema` of changed entities with added, changed and removed fields, type, default and index; the field table is generated |
| Migrations, backfills, flags or cross-repository deploy order | `rollout` | `timeline` with one lane per repository or environment, each step reversible or one-way |
| API, webhook, event or shared-package shapes | `contracts` | `table`: surface, change, before → after, impact (breaking, additive or internal), consumers |
| A status, lifecycle or background job | `lifecycle` | `graph` of states and transitions; a jobs `table`: trigger, schedule, retries, what a second run does |

- Keep one level of detail per diagram and roughly nine boxes, twelve arrows or
  five lifelines. Split instead of cramming.
- Every element that claims a change or a behaviour cites `src`. Unchanged context
  and people need none. The renderer confirms each source at the pinned head,
  including a `#symbol` on those lines, and flags uncited claims. Fix a failing
  citation rather than deleting it.
- Name the real routes, collections, jobs and screens. Tell the story in build
  order: contract, implementation, then consumers.

## The 60-second story

- `users`: what changes for the people who use it, in one or two sentences.
- `why`: the motivation, with its source; say when it is inferred.
- `matters`: the three to five things a reader must know, most consequential
  first, each with its reason (money, permissions, security, data, migration,
  deploy order, concurrency, contract, performance, untested, behaviour) and why it
  matters. Point at a finding when one is the reason. No scores.
- `deploy`: the order to ship and anything that must exist first.

## Decisions

From PR bodies, specs and commit messages, `basis: stated` with the source cited.
Anything concluded from the code alone is `inferred`. Name alternatives only when
a source names them or the trade-off is material.

## Lead merge

The lead adds `findings`, each with `at` anchors pointing where the problem sits
(`visual/element`, or a section when no element fits), plus `requirements`, PR
verdicts, `title`, `summary` and `limitations`. A finding never adds an element to a
diagram. Then `--check`, fix, render.
