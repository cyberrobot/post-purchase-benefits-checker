---
name: pr-workflow
description: Implement and independently review a repository PR specification using an allowance-efficient multi-agent workflow. Use for implementing, reviewing, or repairing spec-driven PRs.
---

# PR Workflow

Use this workflow for spec-driven PR implementation.

## Find the specification

Accept a PR number, PR title, or explicit specification path.

Locate the corresponding specification in the repository.

If exactly one spec clearly matches, use it.

Do not invent requirements that are not in the specification.

## Read context efficiently

Before implementation:

1. Read the complete specification.
2. Read applicable AGENTS.md files.
3. Inspect directly relevant existing implementation.
4. Inspect directly relevant tests.
5. Follow dependencies only where necessary.

Do not broadly read unrelated parts of the repository.

## Implementation

Delegate implementation to the `implementer` agent.

The implementer must:

- implement the complete specification
- stay within scope
- follow applicable AGENTS.md instructions
- reuse existing abstractions where appropriate
- add or update relevant tests
- run targeted tests
- not commit
- not push
- not modify the specification

Prefer targeted tests during implementation rather than the full suite.

## Independent review

After implementation, start a FRESH `reviewer` agent.

The reviewer must independently inspect:

- the complete specification
- the base-to-HEAD diff
- changed files
- applicable AGENTS.md files
- directly relevant surrounding code
- relevant tests and call sites

Review every specification requirement.

Report only concrete actionable findings.

Do not report subjective style preferences.

Do not modify files.

Return:

PASS

or actionable findings ordered by severity.

Keep findings concise.

## Repair

If the first review returns actionable findings:

1. Delegate the findings to the `repairer` agent.
2. The repairer must validate each finding.
3. Fix every valid finding.
4. Run targeted tests.
5. Do not make unrelated changes.
6. Do not commit or push.

Allow only ONE automatic repair cycle.

## Second review

After repair, start a NEW fresh `reviewer` agent.

Do not reuse the first reviewer context.

If the second reviewer returns PASS, continue to final validation.

If the second reviewer still has actionable findings:

STOP.

Show the remaining findings.

Do NOT automatically repair again.

Ask whether the user wants to:
- inspect/fix manually
- run another normal repair
- escalate to the critical reviewer

## Critical review

Use the `critical-reviewer` agent only when explicitly requested or when the user approves escalation.

Suitable reasons include:

- security or authorization changes
- data integrity or migration risks
- concurrency or transaction semantics
- major architectural changes
- unresolved P0/P1 findings
- conflicting reviewer conclusions
- repeated review failure

Do not use the critical reviewer for ordinary PRs.

## Final validation

When review passes:

Run the broader relevant test suite once.

Do not rerun expensive full test suites unnecessarily during every stage.

Finish with:

- PASS or NEEDS HUMAN REVIEW
- implementation model used
- review model used
- number of review cycles
- tests run and results
- concise change summary
- remaining findings, if any

Never automatically commit, push, create a PR, or merge.
