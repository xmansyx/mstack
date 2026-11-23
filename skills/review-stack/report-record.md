# Review Record

One JSON object drives the page, `summary.md` and the saved `review.json`. Write the
compact form; the renderer expands defaults, checks every source against Git, draws
the diagrams and saves the explicit record beside the page.
`render_review.py --example` prints a complete record; `--check` lists every
problem in one run, and `--check --draft` accepts an explorer's partial record.

Text fields are plain text. Identifiers start with a letter and use letters,
digits, `_` or `-`.

## Shape

```json
{
  "title": "…", "summary": "one or two sentences: what the stack builds",
  "limitations": "material checks that failed or could not run",
  "story": {"users": "…", "why": "…", "matters": [{"reason": "money", "text": "…", "finding": "F1", "evidence": []}],
            "deploy": ["…"]},
  "sections": {"architecture": "prose", "data": "…", "rollout": "…", "contracts": "…", "lifecycle": "…", "journey": "…"},
  "prs": [{"id": "api-3121", "repo": "acme/api", "number": 3121, "scope": "reviewed", "title": "…",
           "role": "one line: what this PR contributes", "base": "<sha>", "head": "<sha>",
           "spec_verdict": "…", "code_verdict": "…"}],
  "dependencies": [{"chain": ["api-3120", "api-3121"], "label": "parent of", "evidence": []}],
  "visuals": [],
  "decisions": [{"id": "D1", "title": "…", "why": "…", "alternatives": "…", "basis": "stated|inferred", "evidence": []}],
  "requirements": [{"id": "S1", "pr": "…", "status": "met|missing|diverged|not in spec", "text": "…", "assessment": "…", "evidence": []}],
  "findings": [{"id": "F1", "pr": "…", "severity": "Critical|High|Medium|Low", "title": "…", "explanation": "…",
                "impact": "…", "scenario": "…", "fix": "…", "evidence": [], "at": ["visual-id/element-id"]}],
  "checks": [{"pr": "…", "label": "…", "status": "passed|failed|not run", "result": "…", "evidence": []}],
  "dropped": [{"pr": "…", "concern": "…", "reason": "…"}]
}
```

Arrays may be empty. `resolve_stack.py --output` already wrote `prs` and the parent
chain; build on that file rather than retyping SHAs.

## PRs

`id`, `repo` (`owner/name`), positive `number`, `title`, `scope` (`reviewed` or
`context`), absolute `repo_path` and full pinned `base` and `head`. Reviewed PRs
carry `spec_verdict` and `code_verdict`; `role` is the one line the page shows for
the PR. `url` defaults to the PR on github.com. The resolver writes all of these
except the verdicts and `role`.

## Sources

Anywhere a source is expected (`evidence`, `src`), write a shorthand string:

```
[pr-id:]path:line[-end][#symbol][@base]
```

`src/scan/activate.ts:30-34#activatedAt` cites lines 30–34 at the owning PR's head and
requires `activatedAt` to appear on them. The PR defaults to the claim's own `pr`,
an element's `pr`, or the visual's first `prs` entry; `@base` pins the PR's base.
Ranges stay under 80 lines. The renderer reads every cited range from Git at the
pinned revision; a missing file, a line past the end or an absent symbol fails the
check.

Non-code sources are objects: `{"kind": "requirement", "label", "detail", "url"?}`
(intent from a spec, issue or PR body), `{"kind": "command", "label", "detail"}`
(command, observed output and limits) or `{"kind": "browser", "label", "detail",
"image"?}` (route, role, viewport, state, action, result; an absolute path to a real
PNG/JPEG). Command and browser sources default to the PR head; a passed or failed
check needs one at the reviewed head.

## Visuals

Each visual has `id` (not a section name), `title` (the point it makes), `caption`,
`section` (`overview`, `journey`, `architecture`, `data`, `rollout`, `contracts`,
`lifecycle`), optional `prs` and `evidence`, and one kind. [explainer.md](explainer.md)
says which kind fits which change.

| Kind | Fields |
|---|---|
| `graph` | `nodes: [{id, label, detail?, shape?, status?, tone?, src?}]`, `edges: [{from, to, label?, dashed?, tone?, src?}]`, `note?` |
| `sequence` | `participants: [{id, label, detail?, shape?, status?, src?}]` (2–8), `messages: [{id?, from, to, label, detail?, reply?, tone?, src?}]` (up to 24, numbered) |
| `schema` | `entities: [{id, label, status?, src?, fields: [{name, type?, status?, default?, index?, note?, src?}]}]` (up to 10), `relations: [{from, to, label?}]` |
| `timeline` | `lanes?: [{id, label}]`, `steps: [{lane?, kind?, title, detail?, reversible?, tone?, src?}]` (up to 12, in order) |
| `flow` | `lanes: [{label, steps: [{id?, title, detail?, tone?, arrow?, src?}]}]`, `note?` |
| `table` | `columns: [text]`, `rows: [{id?, cells: [text], tone?, src?}]` |
| `svg` | `svg` string of static primitives, with `evidence`; only when nothing above can say it |

- `shape`: `box`, `store`, `queue`, `external` or `actor`.
- `status` (nodes, participants, entities): `new`, `changed`, `removed` or `untouched`.
- Field `status`: `added`, `changed`, `removed` or `same`.
- `tone` overrides the colour: `normal`, `new`, `changed`, `removed`, `affected` (where a finding bites) or `context` (dashed).
- `dashed: true` draws an asynchronous or event edge; `reply: true` draws a return message.
- Table cells reading `breaking`, `additive`, `internal`, `new`, `changed`, `removed`, `one-way` or `reversible` render as chips.

An element needs `src` when it claims a change or a behaviour: a new, changed or
removed node, entity or field, an affected edge, and every message, step and table
row except `context` ones. People (`actor`) and unchanged context need none. The
page marks an uncited claim with `?` and lists it under its limits; `--check` names it.

## Findings on the page

The page shows each finding as a marker on the elements its `at` names and one
callout (severity, title, impact) under the first of them. `at` entries are
`visual-id/element-id` or a section name. Element ids are node, participant, entity
and step `id`s, `entity.field` for a field, the message or step number in a sequence or
timeline, and a table row's `id`. A finding without `at` appears in the overview.
Explanation, scenario, evidence and fix stay in chat, `summary.md` and `review.json`.

## Checks and dropped concerns

`checks` record what actually ran (`passed`, `failed`) and material checks that did
not (`not run`, with the reason); reading code is not a runtime check. `dropped` is
optional: keep a rejected concern only when a follow-up review would otherwise raise
it again. Both belong to reviewed PRs.

## Example

`python3 "$SKILL_DIR/scripts/render_review.py" --example` prints an illustrative
record with placeholder SHAs. A runnable demo with a real fixture repository:

```bash
python3 "$SKILL_DIR/tests/make_demo.py" /abs/new-demo-directory
python3 "$SKILL_DIR/scripts/render_review.py" /abs/new-demo-directory/input.json
```

Both are synthetic; never treat their content as product findings.
