You are iterating on an **operational design document** for the talos-ops-prod repository — the step that comes *before* `/implement` or `/fix`. The goal is a reviewed, approved design, not code.

Output target: a design document under `docs/` (dated file preferred: `docs/NNNN_YYYY-MM-DD_short-description.md` where `NNNN` is the next free number if a numbered convention exists in `docs/`, otherwise a descriptively-named file). Existing operational notes under `docs/` are the pattern to follow.

Rules:
1. Read `README-LLM.md` first — especially the "Common Operational Tasks", "Common Mistakes to Avoid", and "Networking Architecture" sections. Read every existing doc under `docs/` that touches the same area before writing a new one.
2. Decide where the design lives:
   - Cross-cutting infrastructure change (Cilium mode change, Talos upgrade strategy, new CNI plugin) → new file in `docs/`.
   - App-scoped operational plan (Home Assistant HA setup, Longhorn expansion) → `docs/` with a clear filename.
   - Updating an existing design → edit in place; do not silently duplicate.
3. Scope the design to the request text. If the request is ambiguous, state the ambiguity explicitly and pick the narrowest reasonable scope, calling it out in the PR description.
4. A design doc must cover at minimum:
   - **Problem statement** — what's broken or what capability is missing
   - **Goals / non-goals** — bounded scope
   - **Proposed approach** — concrete manifest / config / task changes with `path:line` citations
   - **Alternatives considered** — with reasons for rejection
   - **Blast radius & rollback** — what happens if the change goes wrong, and how to back out
   - **Prerequisites** — Talos config changes, Renovate PRs to merge first, secrets to add, hardware/cables to install
   - **Open questions** — unresolved decisions
5. Trace every claim to source (`path:line`, `kubectl` output, resource name). Do not describe cluster behaviour from memory.
6. State assumptions up front and validate each one against the actual cluster / actual files. See `core-rules.md` §5.
7. Workflow — follow the Code Change Workflow below: feature branch (`design/` or `docs/` prefix), open a PR, iterate through automated review until it posts APPROVE.
8. **MERGE HOLD — this command never auto-merges.** After the automated review posts APPROVE, STOP. Do not merge. Post a comment on the PR summarising the design and stating it is approved and awaiting an explicit `/merge` from a collaborator. The collaborator decides when to land it (further `/design` invocations can refine before merge).
9. Do NOT write production manifests in this step — only the design doc. If the review surfaces that implementation is needed, say so and recommend a follow-up `/implement` (which will reference this merged design).
