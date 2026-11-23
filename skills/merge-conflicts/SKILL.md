---
name: merge-conflicts
description: Use when a git merge, rebase, restack, or cherry-pick has stopped on conflicts and the hunks need resolving. Covers gh stack and Graphite stack conflicts and post-squash-merge recovery. Do not use for planning a branch strategy or for a clean rebase with no conflicts.
---

# Merge Conflicts

Resolve every hunk from the intent behind each side, not from what looks tidier.

## Workflow

1. **See the current state.** `git status`, which operation is in progress
   (`git rebase --show-current-patch`, `.git/MERGE_HEAD`), which commit is being
   applied, and the full list of conflicting files. Inspect the stack with
   `gh stack view --json`, or `gt log short` for a stack still tracked by Graphite.

2. **Find the primary source for each conflict.** Both sides were written for a
   reason. Read the commit message on each side, then the PR and any linked
   issue or spec. `git log --merge -p -- <file>` shows the commits from both
   sides that touched it. Understand the two intents before writing a resolution.

3. **Resolve each hunk.** Preserve both intents where they compose. Where they
   genuinely conflict, take the one matching the stated goal of this merge and
   say which tradeoff you made. Do not invent new behavior in a conflict
   resolution — a merge is not the place for a third design.

4. **Always resolve.** `--abort` throws away the analysis and the next attempt
   starts from zero. If the resolution is genuinely undecidable, stop with the
   conflict in place and ask, rather than aborting.

5. **Run the project's checks.** Discover them from the repo (`package.json`
   scripts, CI config) rather than assuming. Run checks required by the repo and
   appropriate to the resolved behavior; reuse still-valid evidence.
   A merge that resolves cleanly and fails typecheck is not resolved. Fix what
   the merge broke, and only that.

6. **Finish the operation.** Stage only the resolved, task-owned paths after
   inspecting the index. Resume a gh-stack cascade with `gh stack rebase --continue`;
   for a plain Git rebase use `git rebase --continue`, or commit a merge. Keep going
   until every commit has been replayed and confirm each branch's parent. Finish a
   stack still tracked by Graphite with `gt restack` to the tip.

## Watch for

- **Semantic conflicts with no markers.** Both sides applied cleanly but one
  renamed what the other calls. Typecheck catches most; a shared-package
  signature change may only show up in a consumer repo.
- **Deleted-versus-modified.** Git surfaces this as a conflict with no hunk. The
  deletion usually wins if that path was deliberately removed — verify which
  commit deleted it and why.
- **Lockfiles.** Never hand-merge. Take one side, then regenerate with the
  project's package manager and commit the result.
- **A hunk that reintroduces a deleted path.** Resolving toward "keep both" is
  how a compatibility shim sneaks back in after it was deliberately removed.
- **Force-moved base.** If the trunk was reverted or force-pushed under the
  stack, conflicts multiply and the 3-dot diff understates the real difference.
  Cross-check with `git diff origin/<verified-trunk>..<branch>` before resolving anything.
- **After a squash-merge.** The squashed parent no longer shares commits with
  the child, so the rebase replays work that is already upstream. Confirm what
  actually landed on trunk before resolving hunk by hunk; cherry-picking the
  child's own commits onto a fresh branch off trunk is often less work.
- **Stack tracking.** gh-stack pins each branch's base SHA in `<git-common-dir>/gh-stack`,
  so rewriting a branch outside the cascade leaves it stale — `gh stack view` reports
  `⚠ Needs rebase`. Re-sync with `gh stack rebase`/`gh stack sync` rather than editing
  that state. On a Graphite stack `git branch -f` desyncs `gt` the same way; re-track
  bottom-up rather than fighting it.

## Before declaring done

- [ ] The operation completed. No rebase or merge is still in progress.
- [ ] Required and affected checks pass; unrelated existing failures and proof limits are stated.
- [ ] For each conflict where the intents were incompatible, the tradeoff is stated.
- [ ] No behavior exists in the result that was in neither side.
