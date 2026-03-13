# Mendabot Configuration Issue

## Problem

The mendabot-watcher Deployment has an incorrect `GITOPS_MANIFEST_ROOT` environment variable configuration.

### Current Configuration
- **Environment Variable:** `GITOPS_MANIFEST_ROOT`
- **Current Value:** `k8s/default`
- **Correct Value:** `kubernetes/apps/default`

### Impact

1. **Root Cause:** The mendabot-watcher is configured with an incorrect manifest root path
2. **Effect:** When remediation agent pods are created, they receive the wrong path to search for Kubernetes manifests
3. **Actual Path:** The GitOps repository stores manifests in `kubernetes/apps/default`, not `k8s/default`
4. **Validation:** Running `ls /workspace/repo/k8s/default` returns "No such file or directory", while `ls /workspace/repo/kubernetes/apps/default` shows the correct directory structure

## Evidence

### Deployment Configuration
```bash
kubectl get deployment mendabot -n default -o jsonpath='{.spec.template.spec.containers[0].env}' | jq .
```

Output shows:
```json
{
  "name": "GITOPS_MANIFEST_ROOT",
  "value": "k8s/default"
}
```

### Repository Structure
```
/workspace/repo/
├── kubernetes/
│   ├── apps/
│   │   ├── default/          ← CORRECT PATH
│   │   │   ├── authelia-shadow/
│   │   │   ├── echo-server-shadow/
│   │   │   ├── kustomization.yaml
│   │   │   ├── README.md
│   │   │   └── traefik-shadow/
│   │   └── ...
└── ...
```

### Path Validation
```bash
# Incorrect path (configured in mendabot-watcher)
$ ls /workspace/repo/k8s/default
ls: cannot access '/workspace/repo/k8s/default': No such file or directory

# Correct path (actual repository structure)
$ ls /workspace/repo/kubernetes/apps/default
total 16
drwxr-xr-x.  5 agent agent  120 Feb 27 05:13 .
drwxr-xr-x. 16 agent agent 4096 Feb 27 05:13 ..
-rw-r--r--.  1 agent agent 7768 Feb 27 05:13 README.md
drwxr-xr-x.  3 agent agent   32 Feb 27 05:13 authelia-shadow
drwxr-xr-x.  3 agent agent   32 Feb 27 05:13 echo-server-shadow
-rw-r--r--.  1 agent agent  175 Feb 27 05:13 kustomization.yaml
drwxr-xr-x.  3 agent agent   32 Feb 27 05:13 traefik-shadow
```

## Finding Details

- **Kind:** Pod
- **Resource:** mendabot-agent-e08f4c1c9645-qqd85
- **Namespace:** default
- **Parent:** Job/mendabot-agent-e08f4c1c9645
- **Fingerprint:** `edb99a428bdc`
- **Severity:** medium

## Fix Instructions

The mendabot-watcher Deployment is managed by Helm (release name: `mendabot` in namespace `default`). The fix requires updating the Helm values to correct the `GITOPS_MANIFEST_ROOT` environment variable.

### Option 1: Update via Helm CLI
```bash
helm upgrade mendabot <chart-ref> \
  --namespace default \
  --set watcher.env.GITOPS_MANIFEST_ROOT=kubernetes/apps/default
```

### Option 2: Update via GitOps
If the mendabot Helm values are stored in a separate repository or through a different deployment mechanism, update the values file to change:

```yaml
watcher:
  env:
    GITOPS_MANIFEST_ROOT: kubernetes/apps/default  # Changed from k8s/default
```

### Option 3: Manual Patch (Temporary Fix)
```bash
kubectl patch deployment mendabot -n default \
  --type='json' \
  -p='[
    {
      "op": "replace",
      "path": "/spec/template/spec/containers/0/env/1/value",
      "value": "kubernetes/apps/default"
    }
  ]'
```

**Note:** Option 3 will be overwritten when Helm reconciles the Deployment.

## Verification

After applying the fix, verify the configuration:

```bash
kubectl get deployment mendabot -n default -o jsonpath='{.spec.template.spec.containers[0].env}' | jq '.[] | select(.name == "GITOPS_MANIFEST_ROOT")'
```

Expected output:
```json
{
  "name": "GITOPS_MANIFEST_ROOT",
  "value": "kubernetes/apps/default"
}
```

## Notes

- The mendabot Helm release does not appear to be managed through the main GitOps repository at `kubernetes/`
- This may be installed manually or through a separate automation
- Consider moving the mendabot Helm values into the GitOps repository for better version control and drift prevention
- The `GITOPS_MANIFEST_ROOT` is used by remediation agent pods to determine where to search for Kubernetes manifests in the cloned repository

## Confidence

**Medium** - The incorrect path is clearly documented and verified, but the source of truth for the mendabot Helm values is not in the GitOps repo, requiring manual intervention or deployment through a separate mechanism.
