You are implementing a new feature or configuration change for the talos-ops-prod repository.

Rules:
1. Read `README-LLM.md` before making any changes. It contains the full app-template values reference, SOPS workflow, and manifest patterns.
2. Follow the standard app pattern:
   ```
   kubernetes/apps/<namespace>/<app>/
       ks.yaml                    Flux Kustomization
       app/
           kustomization.yaml     lists all resources
           helm-release.yaml      HelmRelease (usually bjw-s app-template)
           secret.sops.yaml       SOPS-encrypted secret (if needed)
           ingress.yaml           Traefik Ingress (if externally accessible)
   ```
3. Prefer the bjw-s `app-template` chart (currently `5.0.1` in this cluster) unless an upstream chart exists and is preferred. Never write a bespoke Deployment manifest when app-template covers the shape.
4. Every `helm-release.yaml` MUST pin an explicit `chart.spec.version` AND an explicit `values.image.tag`. Never use `latest`.
5. Every `ks.yaml` MUST list its real `dependsOn` — Postgres consumers depend on `cluster-databases-postgres-clusters`, Longhorn consumers on `cluster-storage-longhorn`, etc.
6. Every new app MUST be added to its parent namespace `kustomization.yaml` — Flux won't reconcile a `ks.yaml` that isn't listed there.
7. Every reference to a domain, IP, or shared value MUST use `${VAR}` from `cluster-settings.yaml` or `secret.sops.yaml`. Never hardcode.
8. If the app is externally accessible, protect it with Authelia via the `networking-chain-authelia@kubernetescrd` middleware unless there is a documented reason to bypass. Note the reason in the PR body if you bypass.
9. Never handle or create secrets. Write the skeleton and instruct the user to fill and encrypt.
10. Validate before pushing:
    - `task kubernetes:kubeconform`
    - `grep -c "ENC\[" <any-secret.sops.yaml-touched>` — > 0
    - `grep "^sops:" <same-file>` — must match
11. Leave the repo in zero-drift state: every file listed is used, every `${VAR}` is defined, every `dependsOn` target exists.
