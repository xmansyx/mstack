# PR Writing

Write for a reviewer who has not seen the conversation. Read each PR's current
parent-to-head diff and requirements before drafting. Record the head/base and
available verification evidence so claims stay tied to the work being described.
Use this guide for both new PRs and description updates.

## Title

- Match the repository's title convention and any user-supplied examples.
- Use an action verb and the product's domain language.
- Use `[Area][Feature]` tags only when the surrounding stack uses them.
- Describe the branch's single purpose; avoid “and” joining unrelated work.
- Keep it concise enough to scan in a PR list.

## Description

Lead with the concrete problem and resulting behavior. Explain the trigger and
before/after when useful: who does what, what used to happen, what happens now.
Then explain the mechanism only as far as the reviewer needs to judge it.

A focused fix usually needs one short paragraph plus verification. Larger changes
can use sections for behavior, rollout/risk and validation when those sections
help scanning. Follow a required repository template, but fill it with relevant
information. There is no universal five-section template or target word count.

Use connected prose. Use bullets for distinct changes or checks, not to turn a
sentence into a file inventory. Name a controller, field or helper when it explains
a contract, cause or review risk; a list of edited files belongs in the diff.
Remove implementation jargon the explanation does not need.

Describe the final change. When scope changes, rewrite the title and body around
the final diff. Leave task history, review rounds, model attribution, local
workspace paths and statements like "No new tests were run for this description
update" in the task report. Historical validation still belongs in the PR, with
its actual revision and limits.

State dependencies, deployment order, migrations, public contracts, permission,
money or destructive effects when they matter. Preserve material risk and required
behavior even when shortening. Mention an unchanged path or non-goal only when it
resolves a likely reviewer misunderstanding. Do not give every layer a recap of
the whole stack or present a later PR's behavior as already implemented here.

## Verification

Report observed checks and results, plus material gaps. Name the tested revision
when reusing earlier evidence. Distinguish this branch's checks from integrated
stack-tip results; passing at the tip does not prove each intermediate PR passes.
Do not invent commands, test counts, links or success claims.

Describe the tested behavior and its outcome. A command alone is useful only if
its purpose is clear. Keep pending checks visibly pending; use a separate test
plan only when there are actionable checks left for a reviewer/operator. Do not
duplicate the same evidence under both "Test plan" and "Verification" or list
irrelevant checks as "not run". Say plainly when necessary validation is missing.

## Examples

These are illustrative, not evidence about a real PR. Match the clarity and
level of detail; never copy their facts or test results into another description.

A focused fix, titled **Keep custom field labels in form responses**:

> Opening a form discarded its custom field labels because the response converted
> Mongoose maps into empty objects. Flatten maps when building the response so the
> editor receives the saved labels and a later save preserves them.
>
> Verification: the response regression test passes with custom labels on two
> fields. The browser edit-and-save journey has not been checked.

A stack layer, titled **Validate delivery IDs before sending email jobs**:

> Email jobs with malformed delivery IDs reached the sender and failed after it
> contacted the provider. Validate the ID before sending so malformed jobs fail
> without an external request. The producer correction is in the following PR;
> this layer protects the consumer independently.
>
> Verification: consumer tests pass for valid IDs and reject malformed IDs without
> contacting the provider. The full journey was checked only at the stack tip;
> this intermediate branch has not been tested independently.

## Final description check

After drafting and cutting formulaic filler (an `unslop` skill, if you have one,
does this well), read the exact body file beside the diff:

1. Can a reviewer tell the problem and resulting behavior from the opening?
2. Does each behavior claim belong to this PR, and is every material change covered?
3. Are the necessary risks/order and verification limits accurate and visible?
4. Can any heading, file list, repeated fact or process narration be removed without
   losing information the reviewer needs?

Revise failures before creating or editing PR metadata. This is the writer's check,
not an extra user approval or mandatory second-model review. Check the current
remote head/base immediately before editing; reread the diff if either changed.
Publish the checked body file with `--body-file`, then compare the retrieved title
and body to the prepared title and file. For
[attachments](attachments.md), expect local image paths to
become GitHub URLs; verify captions, placement and the rest of the body, and check
the rendered images. Reconcile other differences or a changed diff before
reporting completion. Keep the checklist in the workflow, not in the PR body.
