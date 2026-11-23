---
name: review-stack
description: Review one or more GitHub pull requests, a stacked PR chain or a cross-repository set before merge. Four parallel risk-lens hunters, an independent check of every finding, and a local explainer page for stacks. Use for any PR, stack, teammate implementation or pre-merge review; not for uncommitted local changes.
---

# Review Stack

Every review is deep by default: all four risk lenses, changed code followed into
its callers, and an independent check of each finding before it is reported. Speed
comes from running those passes in parallel from one shared starting pack, never
from skipping them. Stack and cross-repository reviews also get a local explainer
page showing what the stack builds and how it works.

## Non-negotiables

- Reviews are **read-only** unless the user explicitly requests additional actions.
  A request to fix or post authorizes that stated action; do not ask again merely
  because a skill describes a later approval step.
- Honor the **provided scope**. For an exact PR list, report only on those PRs; ancestors and siblings are context.
- Ask one focused question only when ambiguity materially changes the result. Otherwise start without confirmation.
- Never check out a teammate's branch or disturb a working tree. Pin pull-ref SHAs and inspect them with `git show`, `git grep`, and merge-base diffs.
- Report only verified findings. A plausible but unverified concern is not a finding.
- Findings go in chat. The explainer page explains the system; it never shows code, diffs, approval controls or a findings list.
- Reports are local files outside every reviewed repository. No hosting, uploads, CDN scripts, or remote fonts.
- At most six review workers run at once.

## Workflow

1. **Resolve** each repository with `scripts/resolve_stack.py <owner/repo> <prs> --output /abs/prs.json` from its checkout (`--repo-path` for another clone, `--append` for more repositories, `--previous <last review.json>` on a re-review). It pins every base and head and writes the review pack, `prs.pack.md`, beside the output. [stack-resolution.md](stack-resolution.md) covers overrides and the read-only fallback.
2. **State the scope** in one line; continue when it matches the request.
3. **Launch the wave** in one batch as [review-passes.md](review-passes.md) describes: four hunters, one per risk lens, plus the explainer explorer when the review gets a page. A small single-PR change keeps the lenses with the lead.
4. **While they run**, choose requirements sources (user instructions, linked spec or issue, PR bodies; never create a spec) and check requirements conformance and stack hygiene. Project rules come from the reviewed repository's agent instructions (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`) and any conventions file they point to; [conventions.example.md](conventions.example.md) shows a format hunters can use.
5. **Verify** each hunter's candidates as they arrive, with a fresh verifier per batch. Then read bot and teammate review comments and verify anything they caught that the review missed.
6. **Browser evidence:** for a user-visible frontend change, use `verify-ui` when the app can run safely and a browser would confirm or refute behavior. Report failures; never fix them.
7. **Deliver** Spec then Code in chat, per [reporting.md](reporting.md). For a stack, a cross-repository set or a requested page, merge the findings into the explorer's draft record ([report-record.md](report-record.md)), run `render_review.py --check`, fix every problem in one pass, render, and link the page.
8. **Clean up** the refs the resolver created (`git -C <repo> update-ref -d refs/reviews/pr-<number>`). Return the verdicts, verification gaps and page link.

## Scope rules

- **Named PRs:** Findings only on those PRs; related work is context.
- **This PR only:** Findings only on one PR; ancestors provide context.
- **Full stack:** Review trunk-to-tip, both directions from the supplied PR. Ask if the stack forks and the desired leg is unclear.
- **Whole feature:** Include clear cross-repository siblings. Ask before adding ambiguous siblings.

"Review this PR" does not include every PR by its author. "Review the stack" does not permit posting or fixing.

## Product and lifecycle context

- Require migrations, fallbacks, or backward compatibility only when existing persisted data, deployed behavior, or a public contract is affected. Wholly new, unmerged behavior needs none.
- Respect product boundaries the repository's instructions declare; one product's vocabulary is not another's requirement.
- Search for prior art in the same product family first. Cross-repository citations are valid only after verifying the cited revision.

## Finding standard

Correctness findings need an exact citation and a concrete failure scenario.
Reuse, convention and flow-parity findings also need verified prior art. No PR in
scope may already resolve the issue. Each finding gives an explanation, impact,
scenario, evidence and the smallest correct fix. Report Spec (requirements and
description accuracy) then Code, never reranked together.

Posting requires explicit authorization; otherwise deliver locally. Complete the
concrete report and verify targets before any authorized posting.

## Follow-up reviews

Re-review against the original brief and the ledger of reviewed base/head,
findings, responses and open objections. The resolver names PRs whose patch-id is
unchanged since `--previous`: their review stands and only base-dependent checks
rerun. For changed PRs, review the new commits, their callers and unresolved
findings; broaden only for a material scope, base or contract change. Each round
starts fresh workers carrying the brief, ledger and prior objections. Stop on a
clean review; wording-only edits and declined nits do not trigger another round.
After about three substantive rounds, escalate unresolved serious issues to the
user instead of looping.

Skill maintenance and optional behavioral evaluation belong in [tests/evaluation.md](tests/evaluation.md).
