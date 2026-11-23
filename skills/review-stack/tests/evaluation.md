# Review regression cases

Keep behavior evaluation separate from renderer tests. A valid HTML file does not
prove a good code review. Give each reviewer the same immutable inputs and scope;
withhold expected findings and other reviewers' results.

These are optional recipes for an authorized behavioral evaluation, not a
mandatory gate for each skill edit. Use relevant helper tests for helper changes
and honor a request to judge agent behavior during real tasks.

## Controlled cases

Run `python3 "$SKILL_DIR/tests/make_cases.py" /absolute/path/new-case-directory`.
Give an independent reviewer `request.txt`, `scope.json`, and the generated Git
repository. These cases are synthetic, explicitly labelled, and rerunnable:

| Case | Expected behavior |
|---|---|
| Clean query encoding (#501) | No invented encoding defect; ampersands and spaces round-trip |
| Selection stack (#502/#503) | No unresolved null-handling finding; the later PR supplies the guard |
| Retry UI (#504) | Find the failed-load path leaving the button disabled; support it with source or execution |

Compare baseline and revised skills using the same request and pinned objects.
Score concrete defects found/missed, false positives, correct scope, honest
verification gaps, and whether the reviewer can locate the relevant code in the
report. Record elapsed time without treating one run as a performance benchmark.

## Historical cases

Synthetic cases cannot show what a reviewer misses on real code. Keep a small set
of your own past stacks whose defects are known from later fixes, pinned by head
and parent SHA. Review from Git objects; do not check out the historical commit
or fetch live PR state as a substitute. Use the commit titles and diffs as intent
when the original PR bodies are not supplied.

## Wave changes

Changes to the lenses, the hunter or verifier briefs, or the wave sizing get
measured, not assumed: obvious-looking improvements to multi-agent review often
make results worse. Run the baseline and the revised skill on the historical and
controlled cases and compare defects found and missed, false positives that
reached the chat answer, wall-clock time to the rendered page, and worker count.
One run per case is an anecdote; say so.

## Authoring cost

The record is the expensive artifact: the reviewer types it, and every extra field
or hand-drawn diagram is output tokens. Before the compact form and renderer-drawn
diagrams existed, real reviews wrote 43–64 KB builder scripts with hand-computed
SVG coordinates, rendered up to three times and took several full-page screenshots
to re-check the template.

To re-measure after a change, give an independent reviewer the same completed
findings (title, explanation, impact, scenario, fix, citations) and ask it to
produce the record and report with the current skill. Compare: bytes written to
produce the record, render attempts before success, browser calls, and whether the
verdicts and citations survived unchanged. Store results outside the skill.

## Resolver checks

`scripts/resolve_stack.py` reaches the network, so its topology logic is covered
by unit tests over fixture nodes (`test_resolve_stack.py`): ancestor walking,
fork detection, merged-parent and desync notes, scope flags, checkout selection
and chain dependencies. Verify the live path by hand against a real stack and
compare the printed base/head pairs with `gh pr view`:

```bash
python3 "$SKILL_DIR/scripts/resolve_stack.py" <owner/repo> <open-pr> --output /tmp/prs.json
gh pr view <open-pr> --repo <owner/repo> --json headRefOid,baseRefName
```

## Report checks

Run `python3 -m unittest discover -s "$SKILL_DIR/tests" -v`. Over the synthetic
gift-card stack in `tests/fixture.py`, the tests cover design-doc section order, no
code or review controls on the page, summary/finding agreement, finding markers and
callouts, hover sources at the pinned head despite a dirty working tree, symbol and
line checks, flagged uncited claims, anchor validation, draft checks, context
boundaries, observed-evidence rules, untrusted text, offline output outside the
repository, every diagram kind passing the static SVG sanitizer, and the review pack.

For DOM-level behavior, point the check at an installed `jsdom` (a disposable
directory, or an existing project's `node_modules` read-only):
`node "$SKILL_DIR/tests/test_report_dom.cjs" /path/to/review.html /path/to/node_modules/jsdom`.
It checks navigation against sections, diagram zoom and fit, print state, unique ids
across inline SVGs, internal links, static rendering and resource requests. It does
not prove layout or pixels.

Use `tests/make_demo.py` for a portable example and look at the rendered page in a
real browser at desktop and phone widths: label collisions, wires crossing boxes,
clipped text, marker placement, legends, and the 60-second section above the fold.

For composition changes, give an independent agent a historical stack (pinned SHAs,
findings withheld) and the updated `explainer.md`. Judge the draft record by
whether a reader who never saw the code can say what the stack builds, how data
moves, what deploys first and what is risky, and whether every drawn claim is cited
and true at the pinned head.

Save evaluation results outside the installed skill and product repositories.
State which cases were actually run, distinguish historical from synthetic
inputs, and avoid claiming broad accuracy improvements from this small set.
