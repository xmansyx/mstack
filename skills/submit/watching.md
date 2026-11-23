# Watching and merging a PR

Read this when asked to monitor, babysit or merge a PR. Watching never authorizes
comments, resolving threads, ready-state changes or merging.

## Watch

Handle the existing checks and comments first, then start one watcher and end
the turn. In T3 Code that is `watch_pull_request`; elsewhere, use the harness's
background-task notification, for example a background `gh pr checks <n> --watch`.
One watcher per PR, owned by the thread that works on it; delegated children
never watch. Never write a `sleep` polling loop. Stop the watcher
(`unwatch_pull_request` in T3) before handing off, stopping or asking the user a
question. A merge or close ends the watch.

A watcher that stops because it cannot read the PR has usually spent the GraphQL
rate limit: check `gh api rate_limit --jq .resources.graphql` before watching
again, and never re-watch in a tight loop. REST has a separate limit:
`gh api repos/<owner>/<repo>/pulls/<n>` reads the PR and
`gh api repos/<owner>/<repo>/commits/<sha>/check-runs` reads checks.

## On each wake

- A wake is news, not a merge decision. When an event needs no action, end the
  turn without a message.
- Act only on checks and comments newer than the latest push. Verify each bot or
  reviewer finding against the source before changing code. Fix real findings and
  CI failures; separate repository failures from infrastructure flakes.
- Keep the PR at the size its goal needs. Review loops grow a PR one
  cheap-looking fix at a time: decline unneeded tests, edge-case guards, extra
  compatibility and minor performance work with a written reason, and list them
  as follow-ups. Prefer the fix that deletes or narrows code.
- Post replies only when authorized, in the user's voice. Resolve a thread only
  after its reply posted.
- A watcher can report conflicts without reporting a branch that is merely
  behind. Check `gh pr view <n> --json mergeStateStatus` yourself before calling
  a PR ready.
- If an overlapping PR makes this one obsolete, stop, report it and ask before
  closing.

## Merge gate

Merge only on an explicit request, and only when all of these hold on the latest
head:

- Verification covers every change in the diff.
- Required checks are green.
- Review bots have finished, and each finding is fixed or dismissed with a reason.
- No human review still requests changes.
- The branch is up to date with its base and GitHub reports it mergeable.

Run `git fetch` and recheck right before merging. Never merge when the PR is
behind or dirty, or when base commits that landed after the last green run touch
its files: rebase, push and wait for green again. Use the repository's merge path
(queue, Mergify or stack merge); never `--admin` or another bypass unless the
user asks. A queued or auto-merge request is not a merge: read the PR back until
it reports merged.

Adapted from [tstack babysit-pr](https://github.com/t3dotgg/tstack/blob/11e37a74d0a6868c121cd0910ab2b3bd9873b92a/skills/babysit-pr/SKILL.md)
and [full-send](https://github.com/t3dotgg/tstack/blob/11e37a74d0a6868c121cd0910ab2b3bd9873b92a/skills/full-send/SKILL.md).
