# Review Reporting

## Deliverable

| Reviewed scope | Deliverable |
|---|---|
| One PR in one repository | Findings in chat |
| More than one reviewed PR, or more than one repository | Chat findings plus the explainer page |
| Any scope where the user asks for a report, a link or a page | Chat findings plus the explainer page |

Context PRs do not count: one reviewed PR with twelve ancestors is a chat review.
Findings, severity, citations and the verification gate are the same either way.
For a chat-only review, offer the page in one line when the change has
architecture, schema or rollout worth seeing, and build it if asked.

The page explains; chat judges. The page carries the story, diagrams, decisions,
markers and one-line callouts. The chat answer carries the verdicts and the full
findings, and links the page.

## Two axes

Report **Spec** and **Code** as separate sections, in that order. A change can pass
one and fail the other:

- Code that follows every convention but builds the wrong thing → Code clean, Spec fail.
- Code that does exactly what the spec asked but breaks how this system does it → Spec clean, Code fail.

Never rerank across the two, and state a clean section explicitly. **Spec** carries
requirements conformance plus each PR's description-versus-diff verdict. **Code**
carries every other finding. With no requirements source, say so in one line under
Spec and review Code only.

## Chat answer

Lead with the per-PR Spec verdict, then the per-PR Code verdict, then findings in
severity order (then repository, PR and path) in this format:

```markdown
### <repo> #<PR> — <short problem>
`<file>:<line>`

**Simple explanation:** <what is wrong, in plain English>
**Impact:** <who or what is affected>
**Failure scenario:** <concrete input/action → wrong result>
**Evidence:** <verified code path and relevant cross-PR/prior-art citation>
**Fix:** <smallest correct change>
```

Keep the explanation understandable without reading the implementation, and name
exact affected entry points. Close with material limits in one short note. Leave
test logs and dropped concerns out unless asked. A review with no findings says so
and names residual risks and checks that could not run. When a page was rendered,
give its absolute path and the verdicts and gaps from `summary.md`, unchanged.

## Severity

| Severity | Meaning |
|---|---|
| **Critical** | Security boundary, data loss or corruption, wrong money, or a broadly destructive production failure |
| **High** | Incorrect core behavior, a broken public contract, or a common flow that cannot complete safely |
| **Medium** | Real defect with limited reach, missing regression coverage, avoidable duplication, or maintainability risk with a concrete failure mode |
| **Low** | Small, actionable issue; at most three per PR, never formatter or linter preferences |

Severity follows impact and likelihood, not diff size.

## Verification gate

Before a finding is reported:

- every cited `file:line` is verified at the pinned SHA;
- a correctness finding has a concrete failure scenario;
- a reuse or convention finding names verified prior art;
- no other PR in scope already resolves it.

A passed or failed check needs an actual command or browser observation at the
reviewed head; code that looks right is `not run`. Browser evidence names the
revision, route, role, viewport, state, action and result.

## Render

Write the record in a temporary directory outside every reviewed repository,
starting from the resolver output and the explorer's draft.

```bash
python3 "$SKILL_DIR/scripts/render_review.py" /abs/record.json --check   # every problem in one run
python3 "$SKILL_DIR/scripts/render_review.py" /abs/record.json           # prints the review.html path
```

`--check` validates the record, reads every cited range from Git, confirms cited
symbols and lists uncited claims. Fix everything in one edit, then render. Output
goes to a new directory under `~/.agent/reviews/` (or `--output /abs/new-dir`);
existing directories are never overwritten. Revise by editing the record and
rendering again; never hand-edit the generated files. If rendering fails on the
tooling rather than the record, say which artifact is incomplete and keep the record.

After rendering, read `summary.md` and skim the page's 60-second section: both come
from the record, so the check is that they say what you concluded. The page's zoom,
print and offline behaviour are covered by the skill's tests.

## Posting to GitHub

Post, approve, request changes or mutate a PR only when that action is explicitly
authorized. Finish the report and verify the targets first; prior authorization
remains valid. Before posting an inline comment, confirm the line is in that PR's
diff; put out-of-diff context and prior-art citations in the review body. Submit at
most one consolidated review per PR.
