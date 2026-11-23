---
name: verify-ui
description: Verify changed frontend behavior or layouts in the real app. Also use during review when browser evidence is needed; skip backend-only changes.
---

# Verify UI

Prove the changed experience in a real browser. Verification is evidence, not
an assertion that the code looks right.

## Workflow

1. Determine the exact affected route, entry point, user role, behavior, and
   reference design. Limit the pass to what changed and nearby regression risk.
   Read the accepted scenarios and corrections, then derive affected pages from
   the actual diff and callers. Map each relevant requirement to evidence or a
   stated gap; verifying one checkbox does not establish the whole layout works.
2. Reuse the running app and honor explicit user/repository browser workflows,
   starting with the repository's own verification skill or feature map when it
   has one. Prefer the host's native browser tools (T3 Code's preview tools, for
   example); otherwise use existing project tooling such as Playwright.
   Do not disrupt a user's server or invent a hosted URL. When you start the app,
   read its real URL from the startup output, and remember that a worktree isolates
   files, not databases, queues, ports or credentials. Demonstrate the actual app
   and authenticated route; a wireframe, static imitation or login screen does not
   verify the requested feature.
3. Exercise the primary user flow from its real entry point. Verify visible
   copy, interaction, navigation, persistence, and outcome.
4. Exercise the relevant reverse path: cancel, clear, deselect, back, retry, or
   reopen. Check only affected alternate states such as loading, empty, error,
   disabled, permission-denied, and already-completed.
5. Check desktop and mobile when layout or responsiveness can change. Include
   keyboard/focus behavior when the changed interaction depends on it.
   Check the containing page and navigation, not only an isolated component.
   For stateful flows, run the planned sequence including persistence/reopening.
6. When Figma or screenshots were supplied, compare hierarchy, spacing,
   typography, colors, assets, and responsive behavior against the reference.
7. Inspect console or network behavior when it helps explain a visible failure.
   Capture screenshots or a short recording when they help review the changed
   behavior. Save them in a task-owned location outside tracked source. Keep the
   absolute paths, captions, captured revision, route/state and viewport with the
   verification evidence so another agent can use them. For PR attachments, follow
   [submit attachments](../submit/attachments.md).
8. If implementing, fix failures within scope and rerun the failed path. If
   reviewing or diagnosing, remain read-only and report the evidence.

## Automation and evidence

- Reuse focused Playwright/Cypress/component tests when they exist.
- Add UI automation only when the behavior and regression risk justify the
  maintenance cost and code changes are authorized.
- Do not add screenshot baselines or broad end-to-end matrices by default.
- For generated visual output such as a PDF, inspect the rendered result when
  layout, fonts or bidirectional text matter. Text extraction alone cannot prove
  that a person can read it correctly.
- Report the routes, roles, viewports, states, commands or browser checks, and
  observed results. State anything that could not be verified.
