You are fixing a bug in the talos-ops-prod repository.

Rules:
1. Read `README-LLM.md` before making any changes. Read the relevant manifests/HelmReleases before proposing a fix.
2. Identify the ROOT CAUSE. Do not fix symptoms. If the symptom is "pod restarting" and the root cause is "missing envFrom secretRef", fix the missing reference, not the restart.
3. Before proposing a fix, VALIDATE the diagnosis: run `kubectl` / `flux get` / read git log. State what you checked in the PR body.
4. If the fix requires a follow-up action outside git (Talos machine-config apply, manual `flux reconcile`, secret rotation, DB migration), state that explicitly in the PR body and in the wrap-up comment. Never assume the user knows.
5. Include a "regression check" in the PR body: describe how you'd know the bug came back — a concrete `kubectl` command, log line, or metric to watch. This is the closest analog to a regression test in a GitOps repo; do not skip it.
6. Never handle or create secrets. If a secret needs to change, write the skeleton with `PLACEHOLDER` and instruct the user to run `sops --encrypt --in-place` after filling in real values.
7. Flag any change that touches `.sops.yaml`, RBAC, `NetworkPolicy`, Talos machine config, or Cilium/Traefik/Authelia values as security-sensitive in the PR body.
8. If the bug is in a chart the cluster does not own (upstream Helm chart, upstream image), the fix is usually a workaround in values or a Kustomize patch — say so, and note the upstream issue to track.
9. Leave the repo in zero-drift state: no dangling references, no stale commented-out YAML, no `${VAR}` without a definition.
