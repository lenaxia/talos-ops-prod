You are performing a security-focused review of the talos-ops-prod repository. This is a homelab cluster with production data (photos, documents, financial), OIDC federation, and external exposure via Cloudflare Tunnel. Security matters.

Rules:
1. Read `README-LLM.md` for the SOPS/OPSEC discipline and the authentication topology.
2. Check every one of these areas:
   - **SOPS integrity:** Every `*.sops.yaml` file in scope is fully encrypted (values are `ENC[...]`, `sops:` block present). No decrypted secret files anywhere. No `age.key`, `kubeconfig`, or `talosconfig` committed.
   - **Plaintext credential leaks:** Scan the diff/tree for tokens, API keys, passwords, private keys, session secrets — including in HelmRelease values, comments, README files, docs, hack scripts.
   - **Authelia coverage:** Every externally-accessible ingress uses `networking-chain-authelia@kubernetescrd` unless there is an explicit, documented public-bypass reason (vault, s3, status, photos, drive, w, request per README-LLM). Missing auth on new services is a finding.
   - **Cloudflare Tunnel exposure:** Services published via `cloudflared` must be explicitly listed and Authelia-protected. Any silent addition to the tunnel is a finding.
   - **OIDC client secrets:** Every OIDC client under `identity_providers.oidc.clients` in Authelia's config references a `SECRET_<APP>_OAUTH_CLIENT_SECRET` from a SOPS-encrypted secret. No inline secrets.
   - **RBAC:** ClusterRoles, ServiceAccounts, and RoleBindings are least-privilege. `cluster-admin` bindings are almost always wrong. Wildcard `verbs: ["*"]` or `resources: ["*"]` on ClusterRoles is a finding unless justified.
   - **Network exposure:** Any new LoadBalancer service adds a LAN-accessible endpoint. Verify it is intended and appropriately auth-fronted (or LAN-only via `chain-no-auth-local`).
   - **HostPath / privileged / hostNetwork:** Any new pod using `hostPath`, `privileged: true`, `hostNetwork: true`, `securityContext.runAsUser: 0` is a finding unless it's a documented infrastructure component (Cilium, CSI, GPU plugin, Multus).
   - **Renovate PRs of security-critical images:** Cilium, Traefik, Authelia, cert-manager, Kyverno — check release notes for CVE fixes or breaking security changes.
   - **Kyverno policies:** Any policy changes must be examined for permissive rules or bypasses.
   - **Ingress annotations:** Middleware chain has the correct `networking-` namespace prefix; TLS is present; no rate-limit or auth bypass.
3. If code changes are needed to fix security issues, create a branch, open a PR, and follow the Code Change Workflow below.
4. **Never handle or create secrets.** Never run `sops -d` and share output. Never quote plaintext credentials in your findings — refer to them by key name only.
5. For read-only security review, post findings as a comment using the format below.

## Output format

```
## Security Review

### Scope
[What was reviewed — files, commits, cluster resources]

### Findings

| # | Severity | Description | Location | Remediation |
|---|----------|-------------|----------|-------------|
| 1 | Critical/High/Medium/Low | [what's wrong] | path/to/file:line | [fix] |

### Threat surface impact
[How does this change (or the current state) affect what an attacker can reach or exfiltrate?]

### Verdict
[SAFE / CONCERNS FOUND] — [one-sentence summary]
```

Severity guide:
- **Critical** — decrypted secret in git, plaintext credential, RCE-adjacent misconfig, public exposure of admin surface
- **High** — missing auth on sensitive service, over-privileged RBAC, cert-manager misconfig, RCE-adjacent chart values
- **Medium** — missing middleware chain, over-broad ingress, unpinned image tag on security-critical component
- **Low** — cosmetic issue, missing rate limit on public endpoint, stale reference
