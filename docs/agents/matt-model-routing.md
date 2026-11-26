# Matt skill model routing

OpenCode discovers the project agent profiles under `.opencode/agents/`. The
project's default primary agent is `matt-orchestrator` (GPT-6 Luna, low).
The implementer and spec reviewer use GPT-6.2 Sol, medium; the standards
reviewer uses GPT-6.1 Terra, high. The merger uses GPT-6 Luna, low.

For a single ticket, start a session with the orchestrator and invoke
`@implement` with the issue reference and review base. For a ticket graph,
invoke `@implement-spec` with the parent spec. Both run `@code-review` in the
orchestrator, which launches the two independent reviewers directly.

OpenCode keeps a session's selected model separately from the agent profile.
For an existing session, select `openai/gpt-6-luna#low` via `/models` as well
as selecting the orchestrator. Confirm the session's model selection when
starting a new session; the project default agent alone does not override an
already-selected session model. Configured subagent models apply independently.

Multi-ticket integration requires ticket commits and may require merge commits;
obtain explicit authorization before those operations. Never discard existing
work to prepare a worktree. If a merge cannot be resolved safely, stop and
report it.

Check agent discovery and configured model variants with `opencode debug
agents`. Agent routing is instruction-driven: inspect a representative run to
verify the correct subagents are actually launched. The review profiles deny
the edit tool, but their shell access is not a security sandbox.
