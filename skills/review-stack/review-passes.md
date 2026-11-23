# Review Passes

Every review applies all four lenses, follows changed code into its callers and
callees, and verifies each candidate independently. Parallel workers keep that fast.

## Size the wave

| Reviewed change | Who hunts |
|---|---|
| One PR in one repository, under about 400 changed lines outside tests and generated files | The lead applies all four lenses in one pass; one fresh verifier checks the candidates |
| Anything larger, any stack, any cross-repository set | Four hunters in parallel, one per lens, each across the whole reviewed scope |

Add the explorer from [explainer.md](explainer.md) whenever the review gets a page.
Launch the hunters and the explorer together as subagents; in T3 Code, use
`delegate_task` to reach other providers' models. Workers are read-only and
return text, never edits. Verifiers start as hunters finish, within the cap of six.

## Hunter brief

Every hunter gets the same frame and one lens:

- the request, the scope and the review pack path (`<output>.pack.md`), which
  holds the repository paths, pinned SHAs, diff commands, changed files by kind,
  risk surfaces and PR bodies;
- one lens file: [correctness and concurrency](lenses/correctness.md),
  [money, auth and security](lenses/security.md),
  [data, migrations and contracts](lenses/data.md), or
  [reuse, flow parity and quality](lenses/reuse.md);
- the sections of the project's conventions that the lens names, when the
  project has them.

Instructions for the hunter:

- Read the diff, then follow each changed function into its callers and callees at
  the pinned head, across every PR and repository in scope.
- Report every candidate that could plausibly fail; verification filters them.
  Stay inside the lens.
- Return each candidate as: PR, `path:line` at the pinned head, the claim, a
  concrete failure scenario (input or sequence → wrong result), verified prior art
  for reuse and convention claims, and the smallest fix. Severity is the lead's call.

Bot and teammate review comments and the lead's own notes stay out of every brief
and out of the folder the workers read; the lead reads comments later.

## Verify

A verifier runs on a model from a different provider than the hunter it checks
when more than one is available, and always in a fresh context. It gets that
hunter's candidates and the same pack, and returns confirmed, rejected or
uncertain for each, with the reason. It checks that:

- the citation says what the claim needs at the pinned head;
- the failure scenario follows from the code, traced end to end;
- no PR in scope, earlier or later, already prevents it;
- the reviewed change introduces or worsens it, rather than leaving an older defect untouched;
- for reuse and convention claims, the prior art exists and applies.

The lead decides. A confirmed candidate becomes a finding after the lead spot-checks
its citation; an uncertain one gets the lead's own check or is dropped; a rejected
one stays out. Keep a dropped concern in the record only when a follow-up review
would otherwise raise it again.

## After the review's own pass

Now read bot and teammate review comments (`gh pr view <n> --repo <owner/repo>
--comments`; inline ones through `gh api repos/<owner>/<repo>/pulls/<n>/comments`).
Verify anything they raise that the review missed. Credit nothing unverified and
set severity yourself.

## Lead checks

### Requirements conformance

Assess requirements across the reviewed scope: a criterion met in PR 4 looks
missing from inside PR 2. Use the user's requirements first, then an existing
linked spec or issue, then PR bodies. When a spec or plan is an explicit source,
read it before the diff.

| For each | Check |
|---|---|
| Acceptance criterion | Implemented in this stack? Which PR, which line? |
| Non-goal | Did a PR build it anyway? |
| Named API, route, field or flag | Does the code use exactly that name and shape? |
| Rejected alternative | Did a PR quietly implement it? |
| Diff content not traceable to the requirements | Undeclared scope, only when the source is authoritative and complete |

Statuses: **met**, **missing**, **diverged** (built differently than specified) or
**not in spec**. A divergence is either a bug or a spec update, never silent; when it
looks like an improvement, say the spec needs amending. Where an authoritative
`plan.md` defines the PR split, check the stack matches it.

### Stack hygiene

Use base, ordering and cross-repository checks when the work forms a stack or
crosses deployment boundaries. Check PR metadata for PRs in scope.

| Check | Fail condition |
|---|---|
| Base | A stacked PR based directly on trunk re-includes its siblings' diff |
| Trunk drift | The stack sits on a reverted or force-moved trunk commit; compare `git diff origin/<trunk>..<tip>` with GitHub's diff |
| One idea per PR | The title or body joins two unrelated changes |
| Description matches diff | Every claim in the body is in the diff and every material change is in the body. A body describing absent work is blocking |
| Size | Over about 800 lines without a stated reason |
| Ordering | Nothing depends on a PR above it |
| Cross-repo order | A shared-package PR merges and publishes before its consumers |
| Deploy notes | Index drops, migrations, env vars, SSM parameters and flags appear in the body |
| Local-only changes | No dev tooling, editor or personal config committed |

Formatting, import order and anything the linter or formatter owns are not
findings. Severity definitions and the output contract are in `reporting.md`.
