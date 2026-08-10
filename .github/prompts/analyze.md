You are performing a deep analysis of the talos-ops-prod repository or its running cluster. This is a **READ-ONLY** task — do not make any code changes.

Rules:
1. Read `README-LLM.md` for full architectural context.
2. Read the relevant manifests and query the cluster (`kubectl`, `flux get`, `talosctl`) as needed. Do not describe cluster behaviour from memory — inspect the actual state.
3. Be specific — reference file paths (`path:line`), resource names, namespaces, and data flows.
4. If you find bugs, misconfigurations, drift, or design flaws, describe them precisely with reproduction steps or citations. State the severity honestly.
5. Do not create branches, PRs, or make any file changes.
6. If the analysis reveals issues that should be fixed, suggest using `/fix` or `/implement` in your response.

## Output format

```
## Analysis

### Scope
[What was analyzed — a manifest, an app, a subsystem, a cluster query]

### What I looked at
- `path/to/file:line` — [what I read]
- `kubectl ...` — [what I queried]
- Git history: [what I checked]

### Findings
[Detailed findings with code / resource references. Order by severity.]

### Recommendations
[Suggested actions, if any — reference appropriate commands like `/fix` or `/implement`]
```
