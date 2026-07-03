## Code Change Workflow (MANDATORY)

Every change MUST follow this review-iterate-approve cycle without exception:

1. **Branch** — Create a feature branch (`feat/`, `fix/`, `chore/`, `docs/`, or `refactor/` prefix). Never commit to `main`.
2. **Change** — Make the manifest / values / config change. Follow the app pattern in `README-LLM.md` (`ks.yaml` + `app/` layout, bjw-s app-template values, `${VAR}` substitution, SOPS for any secret). Keep the diff minimal and focused.
3. **Validate**:
   - `task kubernetes:kubeconform` — must pass (if installed locally).
   - For any `*.sops.yaml` touched: `grep -c "ENC\[" ...` must be > 0 and `grep "^sops:" ...` must match.
   - For any Talos machine-config change: note that a `task talos:apply-node` is required post-merge and state so in the PR body.
   - `flux diff` and `flux check --pre` results if the change is bootstrap-adjacent.
4. **PR** — Open a pull request with a clear description. Reference the triggering issue or comment (`Closes #<N>`, `Refs #<N>`). PR body must include:
   - **What** the change does
   - **Why** it is being made
   - **How it was validated** (which commands you ran, what you inspected in the cluster)
   - **Blast radius** — what services are affected and what happens if reconciliation fails partway
5. **Wait for review** — The automated PR review triggers on every PR open and push. Wait for it to complete before proceeding.
6. **Address feedback** — Read every finding. Fix ALL real issues. Push to the same branch — this triggers automatic re-review.
7. **Iterate** — Repeat steps 5–6 until the automated reviewer posts APPROVE.
8. **Merge** — After approval only — merge with squash method, **unless this run was invoked with `--no-merge`** (see Hold below) or it is a `/design` run (which always holds). In a held run, skip merging and post a comment stating the PR is approved and awaiting an explicit `/merge`.
9. **Report** — Post a comment on the original issue/PR confirming completion with a summary of changes and the merged commit SHA.

**Merge control (`--no-merge` and `/merge`):**
- By default `/fix`, `/implement`, `/test`, and `/security` auto-merge after approval (step 8).
- Append `--no-merge` to any of those commands to hold: the run iterates to approval but does NOT merge — it stops and waits for an explicit `/merge`. Use this when you want to eyeball the approved result before Flux picks it up.
- `/design` **always** holds — design docs never auto-merge. Iterate to approval, then await `/merge` (further `/design` invocations can refine the doc first).
- `/merge` is the explicit finalize command: it verifies the latest review is APPROVE (and required CI is green), then squash-merges and deletes the branch. It makes no code changes.

**Hard rules:**
- NEVER merge before the automated review approves — no exceptions.
- NEVER dismiss review findings — fix them or document with concrete evidence why they are false alarms.
- NEVER commit directly to `main`.
- NEVER commit a decrypted `secret.sops.yaml`. If one is on disk, run `sops --encrypt --in-place` first and verify with `grep -c "ENC\["` before touching git.
- All validation (`task kubernetes:kubeconform`) must pass before each push.
- If the review cycle exceeds 3 iterations, step back and reassess the approach — something is wrong with the design, not just the implementation.

**High blast-radius paths** (require explicit callout in the PR body):
- `kubernetes/bootstrap/**` — Talos machine config, initial bootstrap
- `kubernetes/flux/**` — Flux config and variable substitution sources
- `kubernetes/apps/kube-system/cilium/**` — CNI; a bad merge can take pod networking down cluster-wide
- `kubernetes/apps/networking/traefik/**` — primary ingress; a bad merge can break every externally-accessible service
- `kubernetes/apps/networking/authelia/**` — auth gateway; a bad merge can lock everyone out
- `kubernetes/apps/cert-manager/**` — TLS issuance; a bad merge stops certificate renewal
- `.sops.yaml` — encryption config; a bad merge can render all existing SOPS files unreadable

For high-blast-radius PRs, prefer a `--no-merge` run so the human can eyeball and merge manually.
