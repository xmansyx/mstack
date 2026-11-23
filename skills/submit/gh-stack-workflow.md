# GitHub Stack Workflow

Use for authorized code submission. Lookup and metadata-only work stay in
`SKILL.md`; they do not need stack initialization, checkout, rebase or push.

Commands checked against [github/gh-stack v0.1.1](https://github.com/github/gh-stack/tree/v0.1.1)
on 2026-09-13. Consult installed
help when the version differs. The official extension is `github/gh-stack`,
installed with `gh extension install github/gh-stack` when setup is requested.
See the [command reference](https://github.com/github/gh-stack#commands).

## Inspect and map

Keep each PR the smallest coherent, human-reviewable change. Shared contracts
precede consumers. Size prompts a scope check, not arbitrary fragmentation:
around 600 meaningful changed lines justify the boundary; around 800 consider
splitting unless the behavior is indivisible. Exclude generated files/moves.

Verify repository/common directory, worktree ownership, branch, remote and trunk.
Read the current PRs before choosing operations:

```bash
git rev-parse --show-toplevel --path-format=absolute --git-common-dir
git status --short
git diff --cached --stat
git worktree list
git branch --show-current
gh stack --version
gh stack view --json
gh pr list --repo <owner/repo> --state open --limit 100 --json number,title,headRefName,headRefOid,baseRefName,isDraft,url
```

`view` requires local tracking and refreshes its metadata. If no stack is tracked,
inspect the named PRs and branch ancestry first; absence of tracking does not mean
absence of PRs. Query each mapped head explicitly when the list is incomplete.
For read-only lookup, use `gh pr view` without refreshing local stack metadata.
Read native stack membership with `gh api --paginate
'repos/<owner>/<repo>/stacks?pull_request=<PR-number>&per_page=100'`; an API error
is not evidence that the PR is unstacked. Use the verified host for enterprise repos.

Build `repository | branch | parent | local/remote SHA | PR | state | purpose`.
Read each branch's diff against its own parent, not trunk or the stack tip.
Preserve unrelated files and staged changes. Never implicitly stash, discard or
include them. No other writer may mutate the same branches or stack metadata;
worktrees in one common directory can share both.

## Adopt or create local branches

Use the existing tracked stack when it matches. For an existing GitHub stack,
`gh stack checkout <verified-PR-URL>` can fetch and establish local tracking;
inspect its scope before adopting it.

For existing branches, including ones formerly managed by Graphite, verify every
branch exists and record the parent order before adoption:

```bash
gh stack init --base <verified-trunk> <bottom-branch> <next-branch> <tip-branch>
```

`init` adopts existing names but creates missing ones, changes checkout and enables
`rerere`. Pass the trunk explicitly: a repository's default branch can differ from
the stack's actual trunk. Preserve branch names and existing PRs. Resolve stale
ancestry before accepting the map; do not alternate Graphite and gh-stack writes
on the adopted stack or delete old tracking as incidental cleanup.

For authorized new work, initialize the first branch, make its scoped commit,
then use `gh stack add <next-branch>` from the current top to add the next layer.
Use plain Git with an inspected index for commits. Avoid `add -A`, `add -u`, or
`add -m` shortcuts: these can stage broadly or commit on the current layer before
creating the next branch. Never create replacement PRs for fixes to an existing PR.

## Amend and rebase

Switch to the branch that owns the change. Stage only intended paths, inspect
`git diff --cached`, then commit or `git commit --amend --no-edit` as appropriate.
Update the message when the commit's purpose changed. No broad staging or
AI/model attribution.

With a clean worktree, cascade local branch edits without updating trunk:

```bash
gh stack rebase --no-trunk
```

When trunk freshness is required, fetch the verified remote and inspect local
trunk against its remote counterpart first. It must be eligible to fast-forward;
preserve a diverged trunk and resolve ownership/ancestry before proceeding.
`gh stack rebase --remote <remote>` then fetches and rebases the stack from trunk.
Use `merge-conflicts` for conflict reasoning, stage only resolved paths, and
finish with `gh stack rebase --continue` so the cascade resumes. Recheck each
parent diff and rerun checks whose evidence the rebase invalidated.

## Choose publication operations

There is no `--dry-run`, `--update-only`, or `--body-file` on `gh stack submit`
v0.1.1. Do not translate Graphite flags mechanically. Our default separates
branch publishing from PR metadata so descriptions are reviewed before appearing
on GitHub:

| Request | Operations after scope/description checks |
|---|---|
| Update existing PR code | `gh stack push`, edit changed metadata, link verified existing PR URLs only if relationships need updating |
| Create authorized new PRs | `gh stack push`, explicit `gh pr create` for missing mapped heads, then `gh stack link` with verified PR URLs |
| Metadata only | `gh pr edit --body-file`, followed by readback; no stack commands |

Before push, compare `gh stack view --json` to the map: every active branch must
be authorized. Fetch/inspect remote heads and reconcile unexpected commits first;
a lease is not evidence that local code includes someone else's changes. For a
request touching only part of a larger stack, do not push unrelated active layers.
Use scoped Git pushes with explicit leases against the reviewed remote SHAs.

```bash
gh stack push --remote <verified-remote>
```

Push uses per-branch leases but is not atomic. On failure, read all mapped remote
heads before retrying. Keep successful updates; resolve rejected branches without
`--force`, deletion, or recreating PRs. Refresh PR state before each creation so a
partial prior run or concurrently created PR cannot cause duplicates.

For every missing head whose new PR is authorized, publish the checked title/body
against its mapped parent, bottom-to-top. New PRs default to draft unless the user
requested ready for review; preserve the state of existing PRs.

```bash
gh pr create --repo <owner/repo> --head <branch> --base <parent> --draft --title '<title>' --body-file <body-file>
gh pr edit <number> --repo <owner/repo> --title '<title>' --body-file <body-file>
```

The `create` line is for missing authorized PRs; the `edit` line is for existing
ones with changed metadata. Use actual newlines in the file and safe argument
passing for the title. Do not use `--fill` or auto-generated bodies as final prose.

For two or more PRs that need linking, use their verified URLs in full dependency
order and an explicit trunk, from the verified repository:

```bash
gh stack link --remote <verified-remote> --base <verified-trunk> <bottom-PR-URL> <next-PR-URL> <tip-PR-URL>
```

URL arguments identify existing PRs. Branch arguments can push and create PRs,
so do not use them for linking. Linking can change bases and add to an existing
remote stack; inspect its full membership first and verify it afterward. A single
PR needs no link operation. Do not unstack/delete a remote stack to fix a mismatch.

`gh stack submit --auto` creates missing PRs with generated metadata. `--open`
can also mark existing drafts ready. Neither belongs in this default workflow.
`gh stack sync` also fetches, imports remote stack additions, rebases, pushes and
links PRs; reserve it for an explicitly requested full sync whose scope was
checked. It is not a status command or a substitute for update-only submission.

## Read back

Read every affected PR explicitly:

```bash
gh pr view <number> --repo <owner/repo> --json number,url,headRefName,headRefOid,baseRefName,title,body,isDraft,state
```

Compare to the map, prepared titles and exact body files. Confirm remote stack
membership through the stacks API after linking. Warnings or a successful exit
do not prove correct bases.
If native stack support is unavailable, report that limitation and the actual
PRs/branches already published; do not claim a linked stack or silently use Graphite.

Restore starting checkouts unless the user requested particular tips. Return
verified GitHub URLs bottom-to-top with material validation and publication gaps.
