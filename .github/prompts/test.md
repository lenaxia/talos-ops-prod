You are adding or improving validation for the talos-ops-prod repository. This repo does not have a traditional unit-test suite — validation happens through kubeconform, YAML linting, Flux Kustomization health checks, and Renovate release-note analysis.

Rules:
1. Read `README-LLM.md` for the current validation surface.
2. Identify what kind of validation is being requested:
   - **Schema drift** — kubeconform / flux-schemas validation. Add or fix schema references in `helm-release.yaml` / `ks.yaml` headers, or add a manifest to a kubeconform ignore/allow-list.
   - **YAML sanity** — `task kubernetes:validate-yaml` (if the script is fixed — currently has a pre-existing Python bug), yamllint, or a custom `scripts/*.sh` check.
   - **Flux reconciliation health** — add or tighten `healthChecks:` on `ks.yaml` files so Flux waits for the right resource kind.
   - **Runtime probes** — `livenessProbe`, `readinessProbe`, `startupProbe` on the HelmRelease container values.
   - **Custom validation** — a `scripts/*.sh` script exercised in a GitHub Actions workflow.
3. Add validation at the tightest scope that catches the class of failure. A cluster-wide check is worse than a per-manifest check if it dilutes signal.
4. If you find an existing broken validation script (like `scripts/validate-yaml-anchors.sh`), FIX it rather than adding a parallel check. Do not accumulate half-broken validation tooling.
5. If you add a new workflow or task, wire it into the existing `Taskfile.yaml` / `.taskfiles/` structure so it is discoverable.
6. Never handle or create secrets in validation code. Validation of secret files must be structural only (encryption present, sops block present) — never decrypt.
7. Validate that your validation works: run it locally against the current tree AND against a deliberately-broken example. If the check passes both, it's not really checking anything.
