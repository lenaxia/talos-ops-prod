## Core Rules

These rules apply to every response. They are non-negotiable.

### 1. NEVER commit unencrypted secrets

**All secrets MUST be encrypted with SOPS before they touch git. This rule has no exceptions.**

- Secret files are named `secret.sops.yaml` and encrypted with the age key at `age.key` (repo root, gitignored).
- SOPS config is `.sops.yaml`; `.sops.yaml`'s `encrypted_regex` restricts encryption to `data`/`stringData` fields.
- Before staging any `*.sops.yaml` file, both of the following MUST be true:
  ```bash
  grep -c "ENC\[" path/to/secret.sops.yaml   # every value under data/stringData is ciphertext (>0)
  grep "^sops:"    path/to/secret.sops.yaml  # sops metadata block is present
  ```
- If a `secret.sops.yaml` is decrypted, encrypt it before doing anything else:
  ```bash
  sops --encrypt --in-place path/to/secret.sops.yaml
  ```

**When in doubt about whether a file is encrypted, do NOT commit it — stop and verify.** Never paste decrypted secret contents into a comment, response, or prompt. Never run `sops -d` and share the output. Never show `kubectl get secret -o yaml` output — its base64 is trivially decodable. See `README-LLM.md` "Secrets and OPSEC" for the full protocol.

### 2. NEVER perform destructive git operations

Multiple agents or sessions may share this repo.

**Forbidden:**
- `git checkout .` — discards uncommitted work
- `git reset --hard` — destroys work
- `git clean -fd` — deletes untracked files
- `git push --force` on `main` — never, under any circumstance

**Required:**
- Revert files individually and only with explicit user confirmation
- Always check `git status` before reverting anything
- Never commit directly to `main` — every change goes through a feature branch and PR

### 3. Variable substitution — `${VAR}` syntax, never hardcode

Flux performs variable substitution from `kubernetes/flux/vars/cluster-settings.yaml` (ConfigMap) and `kubernetes/flux/vars/secret.sops.yaml` (Secret).

```yaml
# WRONG
host: 192.168.5.12
domain: example.com

# CORRECT
host: ${SVC_TRAEFIK_ADDR}
domain: ${SECRET_DEV_DOMAIN}
```

### 4. HelmRelease versions MUST be explicit

Never use `latest`, floating tags, or unpinned chart versions. Renovate manages automated version bumps through PRs.

```yaml
chart:
  spec:
    chart: app-template
    version: 5.0.1              # exact chart version
values:
  image:
    tag: v1.2.3                 # exact image tag
```

Digest pinning (`@sha256:...`) is acceptable but must still be a real, resolvable digest.

### 5. Assumptions: State, then validate

Every non-trivial claim rests on assumptions. Unstated, unvalidated assumptions cause most cluster incidents.

**Mandatory protocol:**
- State every assumption explicitly before relying on it.
- Validate every assumption — read the source, check the cluster with `kubectl`, inspect the file, or check git history. Do not proceed on an assumption you have not verified.
- If you cannot validate, do not rely on it. Redesign so it is unnecessary, or ask the user.
- Record what proved each assumption (file:line, command output, resource name).

**Red flag words — these signal an unvalidated assumption. When you catch yourself using them, stop and verify:**

- "probably", "likely", "should be", "should work", "I believe", "I assume", "appears to", "seems like", "I think", "presumably", "in theory", "ought to", "most likely", "chances are", "it's safe to assume", "I'm fairly confident", "as expected", "the expectation is", "normally", "typically", "by convention", "standard practice is", "the intent is", "this is meant to", "designed to", "supposed to"

**Never claim what a manifest, chart, or controller does without reading it.** Do not describe behaviour from memory. Read the actual source, trace the actual reconciliation path, query the actual cluster. "I haven't verified this" is an honest answer. An unverified claim presented as fact is worse.

### 6. Validate before applying

Before pushing manifest changes:

```bash
task kubernetes:kubeconform     # validate manifests against schemas
flux check --pre                # (only during bootstrap-level changes)
```

For SOPS files:
```bash
grep -c "ENC\[" path/to/secret.sops.yaml     # must be > 0
grep "^sops:"    path/to/secret.sops.yaml    # must match
```

If validation fails, fix it. Do not push and let Flux report the error — that becomes a red herd in `flux get ks -A` for everyone else.

### 7. Quality assessment

Assess every change against ALL of these dimensions. A deficiency in any one is a finding:

- **Robust** — handles failures, partial states, and adversarial inputs (e.g. Renovate PRs that partially apply)
- **Reliable** — deterministic reconciliation; no dependency on human intervention post-merge
- **Maintainable** — clear naming, `${}` variables, comments only when timeless and necessary; a future you can read it
- **Right-Sized Complexity** — exactly as complex as needed. No premature abstraction. Every reusable Kustomize component or shared Helm value must earn its keep with ≥2 real consumers
- **Secure** — SOPS respected, least-privilege RBAC, no plaintext secrets, no public exposure without Authelia/authn
- **Idiomatic** — follows repo conventions: bjw-s app-template values shape, ks.yaml + app/ layout, ingress annotation format, dependsOn structure

### 8. Explicit over implicit

- Every HelmRelease specifies `interval`, `install.remediation.retries`, `upgrade.remediation`, `uninstall.keepHistory: false` where they matter
- Every `ks.yaml` declares its real `dependsOn` — never rely on incidental ordering
- No commented-out YAML blocks left "for later" without a `TODO(reason):` marker
- Every `Ingress` uses the correct `networking-chain-*@kubernetescrd` middleware — this is a security control, not decoration

### 9. Zero-drift discipline

- Never leave a `secret.sops.yaml` in decrypted state on disk
- Never leave a manifest referring to a `HelmRepository`, `Kustomization`, or `Secret` that does not exist in the tree
- Never introduce a variable in `${...}` form without adding it to `cluster-settings.yaml` or `secret.sops.yaml` first
- If a change requires a Talos machine-config change, say so explicitly; do not silently expect a `talosctl apply` from the user

### 10. Common mistakes to avoid

Ranked by frequency in this repo (see `README-LLM.md` for full detail):

1. Hardcoded IPs or domains
2. Wrong middleware namespace prefix (e.g. `chain-authelia@kubernetescrd` — missing the `networking-` prefix)
3. Forgotten `dependsOn` on a Postgres/Redis/MariaDB-backed app
4. New app not added to its parent namespace `kustomization.yaml` — Flux never sees it
5. Committing a decrypted `secret.sops.yaml` (see Rule 1)
6. `latest` image tags — Renovate can't manage them, Flux won't re-pull
7. Using `service.name` instead of `service.identifier` in app-template v4/v5 ingress paths
8. Missing `strategy: Recreate` on a single-replica RWO PVC deployment — rollout stalls forever
9. Adding new `metallb.universe.tf/*` annotations — MetalLB is NOT deployed, Cilium does LB IPAM. Use `spec.loadBalancerIP` and the `cilium.io/l2-ip-pool` label instead.
