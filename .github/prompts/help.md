Post a comment on the issue or PR with the following content (and nothing else):

---

## AI Assistant Commands

The following commands are available in issue and PR comments:

| Command | Description | Custom Text |
|---|---|---|
| `/ai [text]` | General-purpose — context-dependent. On a PR: full re-review. On an issue: analyze and respond. With text: address the specific request. | Optional |
| `/review [text]` | Explicit code review of the current PR. Append text to focus the review on specific areas (e.g. `/review focus on SOPS handling`). | Optional |
| `/fix <description>` | Fix a specific bug or misconfiguration. Creates a branch, opens a PR, iterates through automated review until approved, then merges. | Required |
| `/implement <description>` | Implement a new app, ingress, or manifest change. Creates a branch, opens a PR, iterates through review until approved. | Required |
| `/test <target>` | Add or improve validation (kubeconform, yaml lint, health checks) for specified target. Creates a branch, opens a PR, iterates through review. | Required |
| `/analyze [text]` | Deep read-only analysis of manifests + running cluster. Posts findings as a comment. No code changes. | Optional |
| `/explain <topic>` | Explain a manifest, controller, or reconciliation path. Posts explanation as a comment. No code changes. | Required |
| `/security [text]` | Security-focused review: SOPS integrity, Authelia coverage, RBAC, ingress exposure, credential leaks. Fixes findings if code changes are warranted. | Optional |
| `/triage [text]` | Triage this issue — categorize, prioritize, assess impact, suggest labels. Posts assessment as a comment. | Optional |
| `/design [text]` | Iterate on an operational design under `docs/` **before** implementing or fixing. Opens a PR, iterates through review until approved, then **holds** — it never auto-merges. Refine with further `/design` invocations, then `/merge`. | Optional |
| `/merge` | Explicitly merge the current PR (squash, delete branch). Verifies the latest review is APPROVE and required CI is green first. Use after `/design`, or after a `--no-merge` run of `/fix`/`/implement`/`/test`/`/security`. | None |
| `/help` | Show this command reference. | — |

**All commands are available to repository owners, members, and collaborators.**

**Merge control:**
- `/fix`, `/implement`, `/test`, `/security`, and `/design` **follow the review-iterate-approve workflow:** branch → PR → automated review → fix → push → re-review → repeat until approved.
- `/fix`, `/implement`, `/test`, `/security` **auto-merge** after approval by default. Append `--no-merge` (e.g. `/implement --no-merge add new home-assistant addon`) to hold the merge until you post `/merge`.
- `/design` **always holds** — designs never auto-merge; post `/merge` to land an approved design.
