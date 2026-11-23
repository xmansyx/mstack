# Stack Resolution

Resolve scope and inspect pinned code without touching a working tree.

## Resolve

One command per repository, run from a clone of it or pointed at one with
`--repo-path`. It reads the repository's whole open-PR topology in one GraphQL
query, walks the chain locally, fetches every in-scope PR into
`refs/reviews/pr-<number>`, and pins each PR's head plus the merge-base its own
diff should be read against.

```bash
SKILL_DIR=<this skill's directory>
python3 "$SKILL_DIR/scripts/resolve_stack.py" acme/api 3121 --output /abs/prs.json
python3 "$SKILL_DIR/scripts/resolve_stack.py" acme/web 42 --repo-path ~/src/web --append /abs/prs.json
```

The repository is `owner/name` on github.com. The checkout's `origin` must be
that exact repository; a fork or another host fails loudly. The chosen path is
saved in the output so the renderer reads the same Git objects.

`--scope` picks who gets findings; ancestors are always included as context:

| Flag | Reviewed |
|---|---|
| `--scope named` (default) | Exactly the PR numbers you passed |
| `--scope this` | The topmost PR only |
| `--scope stack` | Every PR from trunk to tip |

`--trunk` overrides the checkout's configured trunk. Without an override, the
resolver reads the absolute Git common directory in order: `gh-stack` state,
then `.graphite_repo_config`, then `origin/HEAD`. A tracker's trunk can differ
from the GitHub default: a repository can integrate on `dev` while GitHub's
default branch is `main`. gh-stack records a trunk per stack rather than per
repository, so a file whose stacks disagree supplies no default and the next
source is used; a stack created with `gh stack link` alone writes no local state
at all. For a stack targeting another trunk, pass that branch explicitly. If no
default exists, supply `--trunk`; the resolver does not guess.

`--append` merges a second repository's PRs and its
parent chain into the same file, which becomes the record's `prs` and
`dependencies`. Run `--help` for the rest.

With `--output` or `--append`, the resolver also writes the review pack beside the
file (`prs.json` → `prs.pack.md`), one section per repository. For each PR it lists
the diff command, changed files sorted by kind (migration, schema, route, job, code,
ui, config, test, docs; generated files only counted), risk surfaces matched from
paths, specs and issues linked from the body, the patch-id and the body itself.
Every worker starts from the pack. Kinds and surfaces come from paths alone: they
order the reading and are never findings. Bot and teammate review comments are not
in the pack.

`--previous /abs/review.json` (or an earlier `prs.json`) compares patch-ids and
names the PRs whose change is unchanged since that review.

The command writes JSON to stdout or `--output`, and prints the scope report to
stderr. Read those notes before reviewing:

| Note | Meaning |
|---|---|
| `NEEDS RESTACK` | The base branch moved; the PR's own diff starts at the printed merge-base, not its parent's head |
| `FORK above #N` | More than one open child. Ask which leg to review unless the user named the PRs |
| `STACK DESYNC` | The base branch is neither trunk nor an open PR; the merge-base with trunk was used |
| `sits on merged PR #N` | Everything below is already on trunk; the chain stops there |
| `is merged, not open` | An anchor that has landed; it is still reviewed at its recorded head |
| `draft: #N, #M` | Those PRs are drafts |
| `unchanged since the previous review` | Same patch-id as `--previous`: reuse that review; rerun only base-dependent checks |
| `review pack: <path>` | The starting pack every worker reads |

A PR whose checkout is missing, whose remote does not match, or whose number
does not exist fails loudly. Point `--repo-path` at a matching clone; never edit
installed skills or helper scripts to unblock a review.

If the helper is unavailable or fails on tooling, inspect the named PRs with
`gh pr view` and read pinned head/base Git objects directly. Record the exact
scope, ancestry, revisions and any resolution gap; do not silently substitute a
different base or broaden the PR set. A local report can use explicit `repo_path`
and PR metadata.

## Scope modes

- **Named PRs:** Findings belong only to the PRs the user named. Read ancestors, children, and sibling repositories as context only.
- **This PR only:** Review one named PR, using its ancestors as context.
- **Full stack:** Walk trunk to every reachable open child. A fork needs one question.
- **Current branch:** Resolve the current branch's PR, then apply the same rules.

Do not expand an explicit list of PRs because more PRs exist. Expand only when
the user asks for the whole feature or stack, or when a material dependency
makes the supplied scope ambiguous.

## Inspect pinned code

Read Git objects; never check out a branch or modify a working tree.

```bash
git -C <repo-path> diff <base-sha>..<head-sha>          # the PR's own diff, base from the resolver
git -C <repo-path> show <head-sha>:<file>
git -C <repo-path> grep -n <pattern> <head-sha> -- 'src/**'
```

The resolver's `base` is already the merge-base, so a plain `base..head` diff is
correct even on a drifted stack.

## Requirements sources

In order: explicit user requirements and scope; a spec, issue, or acceptance
criteria linked by the user or PR; PR titles and bodies; observable behavior and
established codebase patterns.

Never create a spec for a review. Search for one only when the review references
it or the user asks for requirements conformance. When a spec lives on an
unmerged branch, read it from Git objects rather than a working tree:

```bash
git -C <spec-repo> fetch origin --prune
git -C <spec-repo> show 'origin/<branch>:<path>/spec.md'
```

Absence of a spec is not a defect. Say which sources were used.

## Cross-repository siblings

Search for siblings only for a full-feature review or when contracts cross
repositories:

```bash
gh search prs --owner <owner> --author <login> --state open --limit 60 \
  --json repository,number,title,url
```

Include clear matches with `--append`. Ask one focused question before including
ambiguous work. For named-PR scope, siblings stay context.

## Cleanup

Delete only the refs this review created:

```bash
git -C <repo-path> update-ref -d refs/reviews/pr-<number>
```
