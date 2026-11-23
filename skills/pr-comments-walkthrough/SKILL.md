---
name: pr-comments-walkthrough
description: Walk the user through reviewers' comments on one or more GitHub PRs or a stack one comment at a time — verify each against the code, say whether it blocks, give context and a recommendation, record the user's decision — then apply all decided changes in the PRs that own the code. Use when the user asks to check, go through, or handle review comments on GitHub PRs.
---

# PR Comments Walkthrough

The user decides; you prepare each decision. Nothing is posted, replied to,
resolved, merged or closed on GitHub unless the user asks for that action.

## 1. Collect

- Resolve the PR set (named PRs, a stack, or every open PR of the current work)
  and the reviewer(s) the user means.
- Fetch all three kinds per PR: inline review comments
  (`gh api repos/<o>/<r>/pulls/<n>/comments`), review bodies (`.../reviews`,
  non-empty only) and conversation comments (`.../issues/<n>/comments`). Ignore
  bots unless asked. Keep thread order (`in_reply_to_id`); skip comments the
  user already answered or that are outdated by a later push, and say so.
- Group comments that raise the same topic across PRs; present the group once.

## 2. Verify before presenting

For each comment, read the code it points at on the PR's current head and
anything it depends on. Establish what the code actually does, whether the
concern is real, and whether an earlier user decision or the spec settled it.
Never present a recommendation you have not checked against code.

## 3. Present one at a time

Use this shape, then wait for the user's answer before the next comment:

- **N of M** — where: repo, PR link, file:line (or "PR comment")
- **Reviewer:** the comment, quoted briefly
- **Blocking?** yes / no / effectively yes — with the reason (a question, a
  suggestion, an approval with a note, a conflict with an agreement, a bug)
- **Context:** what the code does today, in plain words; mention a real gap
  the comment exposes even if the comment is only a question
- **Recommendation:** the smallest change that resolves it, its rough size and
  which repos/PRs it touches
- **Your call:** short lettered options (A recommended first), or "nothing
  needed" when an earlier decision already covers it

When the user corrects the premise, restate their model and adjust the
recommendation before recording it. Accept "skip" and move on.

## 4. Record

Keep a decision list in the session scratch area: comment(s), decision, exact
change, owning repos/PRs, defaults and open sub-questions. Show the full list
once every comment is decided, before changing code.

## 5. Apply

Start only when the user says to. Write any shared contract the changes need
first, then put each change in the PR that owns the code and restack the
descendants, following [submit](../submit/SKILL.md) and its gh-stack workflow.
Independent repositories can be handled in parallel. Verify each touched branch
at its own tip, push with leases, update PR descriptions only where scope
changed, and update the spec/plan when decisions change them.

## 6. Reply (only when asked)

Draft one short reply per comment — what changed and where (PR link), or why
not — and show the drafts. Post only after the user approves.
