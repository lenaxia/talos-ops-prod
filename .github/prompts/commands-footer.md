## AI Assistant Commands

The following commands are available on this issue/PR thread. Reply with one to trigger the assistant — any text after a command tunes the request (e.g. `/review focus on the SOPS handling`).

| Command | Description |
|---|---|
| `/ai [text]` | Re-assess this issue/PR in full, or address a specific request (context-dependent). |
| `/review [text]` | Explicit code review of the current PR. Append text to focus on specific areas. |
| `/fix <description>` | Fix a bug: creates a branch, opens a PR, iterates through review until approved, then merges. |
| `/implement <description>` | Implement a feature or manifest: creates a branch, opens a PR, iterates through review until approved, then merges. |
| `/test <target>` | Add or improve validation (kubeconform, task tests, schema drift checks) for the specified target. |
| `/analyze [text]` | Deep read-only analysis (cluster + manifests). Posts findings as a comment. No changes. |
| `/explain <topic>` | Explain a manifest, controller, reconciliation path, or data flow. Posts explanation as a comment. No changes. |
| `/security [text]` | Security-focused review: SOPS handling, RBAC, ingress exposure, Authelia coverage, secret leaks. |
| `/triage [text]` | Triage this issue — categorize, prioritize, suggest labels, link related work. |
| `/design [text]` | Iterate on an operational design under `docs/` before implementing. Opens a PR, iterates through review, then **holds** (never auto-merges). |
| `/merge` | Explicitly merge the current PR (squash + delete branch). Use after `/design` or after a `--no-merge` run. |
| `/help` | Show the full command reference. |

**All commands are available to repository owners, members, and collaborators.**

**Merge control:**
- `/fix`, `/implement`, `/test`, `/security`, and `/design` follow the review-iterate-approve workflow: branch → PR → automated review → fix → push → re-review → repeat until approved.
- `/fix`, `/implement`, `/test`, `/security` **auto-merge** after approval by default. Append `--no-merge` (e.g. `/implement --no-merge new home-assistant addon`) to hold the merge until you post `/merge`.
- `/design` **always holds** — designs never auto-merge; post `/merge` to land an approved design.
- None of these commands ever commit to `main` directly.
