# Issue tracker: GitHub

Specs and tickets for this repository live in GitHub Issues. Use the
`gh` CLI, targeting `cyberrobot/post-purchase-benefits-checker`.

## Operations

- Create: `gh issue create --title "..." --body "..."`.
- Read: `gh issue view <number> --json number,title,body,labels,comments`.
- List: `gh issue list --state open`, using filters as appropriate.
- Comment: `gh issue comment <number> --body "..."`.
- Edit labels: `gh issue edit <number> --add-label "..."` or
  `--remove-label "..."`.
- Close: comment with the explanation, then `gh issue close <number>`.

Use GitHub's native sub-issues and issue dependencies where available.
Otherwise, record `Part of #<parent>` and `Blocked by: #<number>` in
the issue body.

Before creating issues, verify the target repository with
`gh repo view --json nameWithOwner`. Never file issues in the skills
repository unless explicitly requested and authorized.

## Pull requests as a triage surface

PRs as a request surface: no.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Read the corresponding GitHub issue.
