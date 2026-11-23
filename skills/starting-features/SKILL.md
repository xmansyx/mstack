---
name: starting-features
description: Discover the existing flow and reuse before designing or implementing a feature. Define PR boundaries when work will ship as PRs; clarify only material open decisions.
---

# Starting Features

Discover before design and choose delivery before coding. Build the simplest correct feature from existing patterns and coherent reviewable changes.

## Boundaries

- Start with **read-only discovery**. A question, research request, or feature discussion does not authorize code edits.
- An in-conversation discovery brief or PR map is not a spec or plan artifact.
- Match ceremony to scope. A focused feature may need one PR and a short decision summary; do not manufacture a stack or extra machinery.
- Ask only when a missing decision would materially change product behavior, architecture, data, or public contracts.
  Keep it to a short round of focused questions; a clear focused change needs none.

## 1. Discover the current system

Before proposing architecture:

1. State the desired outcome, current problem, explicit non-goals, and success signal.
   Carry forward the user's accepted decisions and corrections, and any recorded
   project lessons that apply; verify their applicability against current code.
2. Identify every repository and consumer likely affected. Read their instructions and current implementation.
3. Verify the exact repository, worktree, and branch, and any named PR, before edits.
4. Trace the nearest analogous flow end to end: UI/client, contract, service, persistence, side effects, reverse/cancel paths, and tests.
5. Search for prior art and reuse: components, types, helpers, services, validators, APIs, jobs, and configuration. Do not accept duplication until existing options are proven insufficient.
   When the project documents implementation entry points or conventions, load the applicable sections and inspect their referenced code in the target checkout. Unverified entries are leads to investigate, not requirements to enforce.
6. Find the source of truth for domain values, defaults, statuses, option lists, mappings, and external data validation.
7. Map cross-repository contracts, package/deployment order, and ownership boundaries.
8. Separate existing persisted/public behavior from wholly new unmerged behavior. Require migration or compatibility only for the former.
9. Verify product boundaries the repositories declare. Do not import one product's vocabulary, lifecycle or architecture into another's core; keep the integration in adapters and consumers.

Summarize the current flow, reusable pieces, constraints, affected surfaces, and open decisions. Cite concrete paths or contracts.

### Pre-edit checkpoint

Before the first implementation edit, state a short decision backed by files you read:

- **Owner:** which existing controller, component, service or module owns this behavior?
- **Reuse:** what will be extended or reused, including applicable validation, domain types, error reporting and UI primitives?
- **New code:** for a new owner or abstraction, name the closest candidate and the concrete responsibility or capability it cannot cover. Search by behavior and callers as well as names; a missing name match is not proof that nothing exists.

One sentence is enough for a focused change. For example: “Extend the existing billing controller and service; follow the service's sanitized error reporting.” This is an autonomous implementation check, not a request for approval or a new plan document. Revisit the decision only if new evidence changes it, and carry it into any subagent handoff.

For UI reuse, check behavior as well as appearance: keyboard access, focus, loading and error states. Extend a suitable existing component when practical; justify a new one when reuse would lose required behavior. File size or a preference for separate files alone does not establish a new responsibility.

## 2. Choose the simplest correct design

Extend the existing flow into the smallest complete end-to-end result. Prefer
existing code, native capabilities and installed dependencies; keep unrelated
improvements separate. Never simplify away validation, data-loss protection,
security, permissions, money handling or accessibility. Ask before deleting
persisted or public behavior.

- For a proposed helper or layer, ask: if it disappeared, would complexity
  disappear too, or would the same responsibility be duplicated across callers?
  Include ordering, errors and invariants in that judgment, not only signatures.
- Walk the next ordinary task the developer or integrator will perform. For
  localization, trace adding one string from its owning app to wherever it is
  edited; for an API, show one realistic caller and result. Count required edits
  and repositories. Eliminate steps caused by duplicated ownership. Do not invent
  a maintenance scenario for a focused change with no such effect.

Compare alternatives only for a real decision. Recommend one and explain the before/after flow and trade-offs.

## 3. Define delivery before implementation

When work will ship as PRs, decide whether it is one PR or a stack. Each PR
must be the **smallest coherent, human-reviewable change**, not an arbitrary
line-count slice. Local implementation or discovery alone needs no PR map.

For PR delivery, create this map in the conversation:

```text
order | repository | target branch/PR | one purpose | depends on | validation
```

Rules:

- One clear purpose per PR; necessary tests and contract changes stay with that purpose.
- Every implementation task, removal, migration, and test belongs to an intended branch before coding.
- Shared contracts precede consumers; cross-repository dependencies state publish/deploy order.
- For an existing stack, map work to the corresponding existing branches. Do not create replacement or fix PRs.
- Write each PR's metadata using [submit's PR writing guide](../submit/pr-writing.md); use the mapped purpose, dependencies and actual verification as inputs.

Implementation should follow this map. Re-slice only when new evidence proves the boundary wrong.

## 4. Plan verification proportionally

Match test depth to behavior and risk. Expected results come from the
requirement or an independent example, not a copy of the implementation's
calculation. Each completion claim needs evidence: the revision, command or
browser action, and observed result. For PR delivery, state what is verified per
PR and at the integrated tip.

Keep a compact mapping of accepted behavior to implementation and evidence; use
the existing plan or task list when present. Carry it into delegated work and
verification so a narrower worker brief cannot silently drop a requirement.
For lifecycle work, include the sequence that changes state over time, not just
each operation alone. For example: create a draft order → add an item → apply a
discount → cancel the order.

For user-visible frontend work, include `verify-ui` after implementation. Name
the affected flow, relevant states, and desktop/mobile viewports when responsive
behavior can change.

## 5. Continue according to the request

- If the user requested a spec or plan, write it from the verified discovery and include non-goals, decisions, affected surfaces, verification, and a PR map when PR delivery is in scope.
- If the user requested implementation, continue through verification. Follow
  the delivery map when PRs are in scope; routine branch and task mapping needs
  no additional approval.
- At submission, use `submit` to validate and publish the planned structure.
- Use `review-stack` for an evidence-backed review of existing PRs, not as a substitute for feature discovery.

## Stop conditions

Stop only when a product decision, destructive schema/public-contract change, stack ambiguity, or unsafe branch mapping cannot be resolved from evidence. Otherwise proceed.
