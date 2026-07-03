You are explaining a manifest, controller, reconciliation path, or data flow in the talos-ops-prod repository. This is a **READ-ONLY** task — do not make any code changes.

Rules:
1. Read `README-LLM.md` for the full architectural context.
2. Read the relevant manifests and cluster state before answering. Cite `path:line` for every claim.
3. Be clear and specific — reference files, resource kinds, HelmReleases, Kustomizations, and data flow.
4. If the explanation reveals issues (misconfig, drift, tech debt), note them but do NOT fix them. Suggest `/fix` or `/analyze` for follow-up.
5. Do not create branches, PRs, or make any file changes.
6. Prefer diagrams-as-text (arrow chains, tables) for reconciliation and networking paths — they read well in GitHub comments.

## Output format

```
## Explanation

### Topic
[What you were asked to explain]

### The short answer
[1–3 sentences]

### The full story
[Detailed walkthrough with file references, resource names, and reconciliation flow]

### Related
[Related files, worklogs, upstream docs — with links or paths]
```
