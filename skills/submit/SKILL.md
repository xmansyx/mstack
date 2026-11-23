---
name: submit
description: Prepare, submit or update GitHub PRs and stacks with gh stack; write and check descriptions, attach screenshots or videos as useful evidence, and return verified PR links.
---

# Submit

Choose the requested operation before loading detailed procedures or changing
anything. A request for links or descriptions must stay small.

| Mode | Work allowed by the request |
|---|---|
| Lookup/status | Read named PRs and relevant stack relationships; return verified links/status. No checkout, tests, restack or push |
| Prepare | Inspect requested changes, propose PR boundaries and draft metadata in the response. No repository or remote mutation |
| Metadata only | Read each named PR's own current diff and requirements, update title/body with `gh pr edit`, then read it back. Preserve code, bases and draft/ready state |
| Submit code | Commit/push authorized changes to the mapped branches and verify the remote stack using the workflow below |

## Write before publishing

For every title/body you create or update, read [pr-writing.md](pr-writing.md)
before drafting. Lead with the concrete problem and resulting behavior. Match
detail to the diff; a small fix usually needs a short paragraph and validation.
Use the guide's final description check on the exact body file, then publish
that file and read the remote body back. Commit messages and CLI
generated descriptions are inputs to inspect, not finished PR descriptions.

Existing validation may be reported with its revision and limits; do not run
tests solely because prose changed. If the remote head or base changes during
writing, inspect the new diff before editing the description. Preparing text
alone does not authorize publishing it.

For code submission, preserve the named PR/branch map and update existing PRs
when they own the change. Use [gh-stack-workflow.md](gh-stack-workflow.md) for
adoption, restacking and publication; resolve material mapping ambiguity first.

## Screenshots and recordings

When attaching useful UI evidence, read [attachments.md](attachments.md) for
capture provenance, privacy, CLI support, upload commands and partial-failure
recovery. Preserve uploaded URLs when editing descriptions. Read-only and
draft-only requests do not authorize uploads.

## Code submission

1. Verify repository/common directory, checkout, branch, trunk and current PR
   state. Preserve unrelated changes and map every authorized branch to its
   parent, PR, purpose and state.
2. Put each fix in its owning PR. Stage intended paths and inspect the complete
   index; follow [gh-stack-workflow.md](gh-stack-workflow.md) for commits,
   restacks, leases and publication. Do not replace an existing stack.
3. Keep PRs coherent and reviewable. Check their own diffs, requirements, reuse
   and error reporting. Reuse applicable checks; verify uncovered integrated
   behavior and changed UI through the appropriate skills.
4. Finish titles/bodies using the writing guide, publish the exact checked body
   file and read remote head/base, metadata and draft/ready state back. Verify
   every remote parent against the map; restore starting checkouts as appropriate.
5. Return verified URLs in dependency order, with material verification gaps.
   Complete evidence uploads, then remove a task-owned worktree only when
   implementation is complete and no session or running process still needs it.
   Metadata/lookup work does not trigger cleanup.

Never create unsolicited specs/plans, sweep unrelated changes, or submit known
broken work without the user's acceptance of the named failure. Merge, close,
comments and ready/draft changes require an explicit request; prior authorization
persists. Do not force-rewrite a diverged trunk or delete branches to submit.

For a submission, report readiness only when code evidence remains applicable and
the final remote map matches the requested scope. For metadata or lookup work,
report completion of that operation without implying the code was newly verified.

## Linking and monitoring

In T3 Code, register every PR created or worked on with `link_pull_request`,
including each stack layer, and compare `list_thread_pull_requests` before
completion. `gh stack link` does not register a PR with T3.

When asked to monitor, babysit or merge, read [watching.md](watching.md): one
watcher owned by the parent, what to do on each wake, and the merge gate.
Delegated workers return URLs/head SHAs/check state and leave watching to the
parent. Monitoring does not authorize comments, resolving threads, ready-state
changes or merging.
