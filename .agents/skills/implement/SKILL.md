---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

Coordinate implementation of the work described by the user in the spec or tickets.

If the user passes a ticket reference, fetch it from the issue tracker and state its title before starting. If the reference is ambiguous, ask.

Delegate the implementation to a fresh `matt-implementer` subagent. Give it the
ticket/spec reference, pre-agreed test seams, working directory, and permission
boundaries. Ask it to load the `tdd` skill where possible.

Have the implementer run typechecking and focused tests as appropriate; run the
broader relevant test suite once after implementation.

Once done, call the Skill tool with "code-review" from the orchestrator to review
the work using the named reviewers. Provide the fixed base and include uncommitted
changes in the review. Delegate validated fixes to a fresh `matt-implementer`.

Commit work to the current branch only if explicitly authorized by the user.
