# Global rules

An example of the personal rules these skills were written alongside. Copy what
you agree with into `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` or a project's
`AGENTS.md`, and delete the rest. Several skills assume the request-intent,
verification and Git rules below.

## Request intent and ceremony

- Treat questions, reviews, diagnoses, and status requests as read-only unless I explicitly ask for changes.
- Handle straightforward work directly. Write a spec or plan artifact when I ask for one.
- Match the process to the task. Handle focused work directly; use subagents, worktrees, and multi-pass reviews only when the scope benefits or I request them.
- For implementation requests, continue through implementation, affected checks, inspection of the running result when relevant, and correction of in-scope failures. Report remaining verification gaps. Reviews and diagnoses finish with evidence-backed findings unless changes are requested.
- Lead a fix proposal with the minimal option: files touched and rough diff size.
  Upgrades come after, each with the condition that would justify it.
- For non-obvious fixes, explain the root cause and the before/after behavior simply.

## Starting feature work

- Before designing, specifying, planning, or implementing a new feature, use the `starting-features` skill.
- Start with read-only discovery.
- Inspect the current implementation, nearest analogous flow, reusable code, cross-repository contracts, and product boundaries before proposing architecture.
- For behavior changes or new abstractions, identify the existing owner and reuse relevant code before editing. For typos and mechanical edits, inspect the affected code without a formal discovery checkpoint.
- When work will ship as PRs, define the smallest coherent, human-reviewable slices before coding and assign every task to its intended branch.
- Ask about product intent or a material design decision only when it is genuinely unclear. A clear focused change needs no interview.

## Workspace and Git

- Before editing, verify the exact repository, worktree, and branch. Resolve the
  repository by its full git-common-dir path, and honor any named PR or branch.
- Keep commit messages short and human. Never add AI, model, harness, or agent
  attribution, including `Co-Authored-By`, unless I explicitly request it.
- Stack and submit pull requests with `gh stack` through the `submit` skill. Use
  Graphite only to read or repair a stack it already owns, and never alternate the
  two tools on one stack.

## Engineering

### Simplicity
- Make the smallest complete change that meets the current requirement. Prefer
  existing code, native capabilities, and installed dependencies before adding
  code or packages. Keep unrelated improvements separate.
- Before proposing a fix, read the code that fails and cite it as `file:line`.
  State the smallest diff that changes that line's behaviour. Anything larger is
  a second option with a stated reason, never the default proposal. A mechanism
  you inferred but have not read is not a basis for a plan: close that gap first.
- Never simplify away input validation, error handling that prevents data loss,
  security, permissions, money handling, accessibility, or anything I explicitly
  asked for.
- Before finishing, compare new controllers, components, services and helpers with the reuse decision. Remove unnecessary duplication and layers introduced by the task without weakening required behavior.
- Share code when it represents the same domain rule or responsibility. Similar-looking code alone does not justify a generic abstraction.
- Grow the system in layers. Start from the smallest version that works end to
  end, then add each capability on top of something that already works. Keep the
  product working at every step.
- Keep components modular and concerns separated.
- Prefer a direct synchronous flow when it is correct. Add a queue, background
  job, event, adapter, state machine, flag, or extra layer when the current
  requirement needs it.

### Comments
- Prefer clear names and structure over explanatory comments. Comment only the
  non-obvious why, invariant, constraint, or necessary workaround.
- Every comment earns its place by saying something the code itself cannot show.

### Tests
- Match test depth to behavior and risk. Cover new behavior, regressions,
  important boundaries, integrations, and realistic failure modes.
- Each test protects a behavior or failure that matters. Test count and coverage
  numbers are not the goal.
- Expected results come from the requirement or an independent example, not a
  copy of the implementation's calculation. Cover a realistic sequence when
  earlier actions change the state a later action reads.
- A test earns its place when it fails if the behavior breaks and still passes
  when only the internals change. Rewrite or delete one that does neither.
- Never skip, delete, loosen or rewrite a test, assertion, checker config or CI
  step to get green. Fix the code, or report the failure.
- After user-visible frontend changes, use `verify-ui` before claiming the work
  is complete. Verify the real affected flow and relevant states/viewports.
- Add UI automation, screenshot baselines, or broad end-to-end suites when the
  regression risk justifies the maintenance cost.

### Verification and continuity

- Match each completion claim to inspected evidence: the relevant code revision,
  inputs, environment, command or browser action, and observed result. A focused
  check proves its scope; report unverified parts explicitly.
- Reuse valid evidence while the code, dependencies, inputs and environment it
  covers are unchanged. Rerun affected checks after changes that invalidate it;
  a new message or agent handoff alone does not invalidate a result.
- After a rebase or restack, an unchanged `git patch-id` means the change itself
  is the same, so its review still applies. Checks that depend on the base still
  rerun on the new head.
- Check accepted requirements against the finished experience, not just passing
  tests. Before handing off, preserve scope, decisions, remaining work, exact
  repositories/branches/PRs and verification. Recheck mutable facts on resume.
- A worktree isolates files, not databases, queues, ports or credentials;
  localhost may be a tunnel to shared infrastructure.

### Type safety and sources of truth

- In typed code, model the real shape and validate uncertain external data at the
  boundary. `any`, double casts, non-null assertions, and lint/type suppressions
  are not available for silencing a modelling problem: fix the model.
- Before introducing a hardcoded domain value, default, status, option list, or
  mapping, find the existing source of truth and nearest analogous flow.

### Dependencies
- Reach for the standard library and native platform features before any
  dependency, and for dependencies already in the project before adding a
  package. Check a library's documentation and types before concluding it lacks
  a capability.
- Prefer established, well-maintained libraries when they reduce overall
  complexity or improve reliability. Reimplementing common functionality needs a
  stated reason.

### Removing obsolete code
- Default is DELETE. Remove the old path outright. Backward compatibility — a
  compatibility layer, fallback, dead flag, or `legacy` branch that keeps the old
  path alive — ships only when I approve it.
- Ask before deleting a persisted field, migration, public API, auth or permission
  flow, or published export unless I have explicitly authorized that deletion and
  its impact. Ask again only if the scope or consequences change.

### Architecture
- Make architectural decisions for the long term. A design you already plan to
  replace is the wrong design.
- Commands, lifecycle steps, and processing loops converge to the same end state
  regardless of crashes, restarts, retries, or partial prior runs.
- When concurrent actors could write the same file, branch, key, or state object,
  eliminate the sharing first. Serialize behind one writer only when that is a
  real invariant.
- Reuse existing tools for checks and migrations. Create a reusable script or
  codemod when repeated operations, complexity, or reproducibility justify it.
