# PR screenshots and recordings

When visual evidence helps explain a UI change, attach captures from
[verify-ui](../verify-ui/SKILL.md) to the PR description. Use before/after images
when both were captured from the relevant revisions; label integrated stack-tip
evidence accurately. Inspect captures for unrelated private data before uploading.
Attaching relevant evidence is part of an authorized PR submission or description
update; a read-only review or draft-only request does not authorize uploading it.

Use native `gh pr create/edit --attach` (GitHub CLI 2.99.0+). Check that
`gh pr edit --help` lists `--attach` on the executing host. Uploads require
GitHub.com or GHE.com, repository write access, and user OAuth/PAT credentials;
GitHub App tokens, including the default Actions token, are unsupported.

Write image references into the prepared body, for example
`![Updated checkout](./evidence/after.png)`, then attach the same local paths:

```sh
gh pr edit <PR-URL> --body-file <BODY-FILE> --attach ./evidence/after.png
```

Repeat `--attach` for multiple files. Paths resolve from the command's working
directory; absolute paths also work. GitHub replaces matching Markdown paths with
uploaded URLs. To append evidence while preserving the current body, use `--attach`
without `--body-file`. Keep the resulting URLs when making later description edits.

Read back the body and check that images render in the PR; report any rendering
check you could not perform. An upload can partly succeed even when the command
exits non-zero: inspect the remote result before retrying, and retry only missing
attachments. If uploading is unavailable, retain the local evidence and report
the limitation; never publish broken local-path embeds.

Reference: [GitHub CLI attachments](https://docs.github.com/en/github-cli/github-cli/attaching-files-with-github-cli).
