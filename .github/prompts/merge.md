You are finalizing an already-reviewed pull request for the talos-ops-prod repository via an explicit `/merge`. This command makes no code changes — it only merges an approved PR.

Rules:
1. This command runs on a PR thread. Identify the current PR (e.g. `gh pr view`).
2. **Verify approval before merging — no exceptions:**
   - Check the latest automated review state. The most recent review from the AI reviewer MUST be **APPROVE**. If the latest review is `REQUEST_CHANGES`, `COMMENT` with open findings, or there is no review yet, DO NOT merge.
   - If not approved: post a comment stating the current review state and what remains (e.g. "Latest review is REQUEST_CHANGES — resolve the open findings and re-review before /merge"). Stop. Do not merge.
3. Confirm the PR branch is not `main` and that all required CI checks are green (or note any non-blocking skipped checks). If a required check is failing, DO NOT merge — report it and stop.
   - Ignore CI failures that are demonstrably unrelated to the diff (e.g. an upstream Homebrew "untrusted tap" error in `configure (talos)` that also fails on `main`). State the reason for the exemption in your comment.
4. Merge with the **squash** method: `gh pr merge <N> --squash --delete-branch`.
5. If the merge is blocked by GitHub (branch-protection, behind main, merge conflict), report the exact blocker in a comment and stop. Do not force-push or force-merge.
6. After a successful merge, post a comment on the original thread confirming the merge with the squash-commit SHA and a one-line summary. If this PR was triggered by an issue, link back to that issue.
7. If the merge changes anything under high-blast-radius paths (see `code-change-workflow.md`), post a follow-up reminder in the comment: e.g. "This change requires `task talos:apply-node` on affected workers" or "Cilium DaemonSet will roll — verify `kubectl -n kube-system get pods -l app.kubernetes.io/name=cilium` afterwards".
8. Never use `git push --force`. Never commit directly to `main`.
9. Do not modify files, tests, or the PR diff in this step. `/merge` is a finalize-only operation.
