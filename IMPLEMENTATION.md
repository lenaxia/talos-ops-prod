# Certificate Rotation System Implementation

This document describes the complete automated certificate rotation system for Talos and Kubernetes client certificates.

## Overview

The system provides automated monthly rotation of:
1. **GitHub deploy token** (1 month validity) - Used by cluster to commit changes
2. **Talos admin client config** (1 year validity) - Admin access to Talos API
3. **Kubernetes admin client config** (1 year validity) - Admin access to Kubernetes API

## Architecture

```
┌─────────────────┐          ┌─────────────────┐
│  GitHub Actions  │          │   Talos Cluster  │
│                 │          │                 │
│  Monthly:        │          │  Monthly:       │
│  1. Generate    │          │  1. Generate    │
│     GitHub token  │          │     talosctl     │
│  2. Encrypt with │          │     config         │
│     SOPS/age    │          │  2. Generate     │
│  3. Commit to    │──────────│     kubectl config  │
│     gitops repo   │          │  3. Commit both  │
└─────────────────┘          │     to gitops     │
                           │     repo using      │
                           │     GitHub token    │
                           └─────────────────┘
```

## Components

### 1. GitHub Actions Workflow
**File:** `.github/workflows/rotate-github-token.yaml`

**Schedule:** Monthly (1st day of month at 2:00 AM UTC)

**Features:**
- Generates GitHub App JWT token using RS256 signature
- Encrypts token with SOPS using age public key
- Updates encrypted secret in gitops repo
- Commits changes with configurable author

### 2. Kubernetes CronJob
**File:** `kubernetes/bootstrap/cert-rotation/cronjob.yaml`

**Schedule:** Monthly (1st day of month at 2:00 AM UTC)

**Features:**
- Runs in `cert-rotation` namespace
- Generates new talosctl config (1 year validity)
- Creates and signs Kubernetes CSR (1 year validity)
- Commits both encrypted configs to gitops repo
- Sends notifications on success/failure
- Configurable retry logic (default: 3 retries)
- Optional namespace cleanup after successful rotation
- Sends Prometheus metrics to AlertManager

### 3. RBAC Configuration
**File:** `kubernetes/bootstrap/cert-rotation/rbac.yaml`

**ServiceAccount:** `cert-rotator` (cert-rotation namespace)

**ClusterRole:** `cert-rotator`

**Permissions:**
- Create, get, list, watch CertificateSigningRequests
- Approve CertificateSigningRequests
- Approve signers (kubernetes.io/kube-apiserver-client)
- Get namespaces and services (for kubeconfig)
- Read secrets (kubeconfig and talosconfig templates)

### 4. Configuration Management
**File:** `kubernetes/bootstrap/cert-rotation/configmaps.yaml`

**ConfigMaps:**
1. **cert-rotator-config** - Main configuration:
   - Git repository: `lenaxia/talos-ops-prod`
   - Git author name: `cert-rotator`
   - Git author email: `cert-rotator@users.noreply.github.com`
   - Certificate role: `admin`
   - kubectl context name: `admin-client`
   - Talos endpoints: `192.168.3.10,192.168.3.11,192.168.3.12`
   - Kubernetes API server: `https://192.168.3.10:6443`
   - Certificate TTL: `8760h` (1 year)
   - Rotation namespace cleanup: `false`
   - Max job retries: `3`
   - Monitoring configuration

2. **talosconfig** - Talos admin config:
   - Contains embedded CA and client certificates (encrypted placeholders)

3. **talos-admin-kubeconfig** - Kubernetes kubeconfig template:
   - Base kubeconfig with placeholder for CA and credentials

4. **cert-rotator-author-config** - Notification secrets:
   - Pushover user key
   - Pushover prod token

## Secrets

### GitHub Token Secret
**File:** `kubernetes/bootstrap/secrets/github-token.sops.yaml`

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: github-deploy-token
  namespace: flux-system
type: Opaque
stringData:
  token: PLACEHOLDER_REPLACED_BY_ACTIONS
  username: x-access-token
```

### Client Configs
**Talos Client Config:** `kubernetes/bootstrap/client-configs/talos-client-config.sops.yaml`

**Kubeconfig:** `kubernetes/bootstrap/client-configs/kubeconfig.sops.yaml`

## Deployment Steps

### 1. Create GitHub App

1. Go to GitHub repository settings → Developer settings → GitHub Apps
2. Create new GitHub App:
   - App name: `gitops-cert-rotator`
   - Repository permissions: Contents (Read & Write)
   - Install only on: `lenaxia/talos-ops-prod`
3. Copy the following secrets:
   - `GH_APP_ID` (numeric ID)
   - `GH_APP_PRIVATE_KEY` (PEM private key)
   - `GH_APP_INSTALLATION_ID` (installation ID)
4. Add to GitHub repository secrets:
   - `GIT_AUTHOR_NAME`: Git commit author name (e.g., `"cert-rotator"`)
   - `GIT_AUTHOR_EMAIL`: Git commit author email
   - `SECRET_PUSHOVER_USER_KEY`: Pushover user key
   - `SECRET_PUSHOVER_PROD_TOKEN`: Pushover prod token

### 2. Apply Kubernetes Manifests

```bash
# Apply all manifests
kubectl apply -k kubernetes/bootstrap/cert-rotation/

# Verify deployment
kubectl get all -n cert-rotation
```

### 3. Initial Rotation

The GitHub Actions workflow will run automatically on the 1st of the month. After first run:

1. GitHub token is generated, encrypted, and committed
2. Flux detects and applies updated `github-deploy-token` secret
3. CronJob runs and generates new client configs
4. New configs are committed to gitops repo
5. Flux applies new `talos-client-config` and `kubeconfig` secrets

### 4. Manual Rotation Trigger

To manually trigger rotation:

```bash
# Via GitHub Actions
gh workflow run "rotate-github-token.yaml"

# Via CronJob (immediate run)
kubectl create job --from=cronjob/cert-rotator -n cert-rotation
```

## File Structure

```
talos-ops-prod/
├── .github/
│   └── workflows/
│       └── rotate-github-token.yaml       # Monthly: GitHub token rotation
├── .sops.yaml                               # Updated with cert rotation rules
├── kubernetes/
│   ├── bootstrap/
│   │   ├── secrets/
│   │   │   └── github-token.sops.yaml  # Updated by Actions
│   │   └── cert-rotation/
│   │       ├── namespace.yaml              # cert-rotation namespace
│   │       ├── github-token-secret.yaml    # GitHub token secret
│   │       ├── rbac.yaml                   # ServiceAccount + Roles
│   │       ├── configmaps.yaml            # ConfigMaps
│   │       ├── kustomization.yaml         # Kustomization
│   │       └── cronjob.yaml              # Rotation CronJob
│   └── client-configs/
│       ├── talos-client-config.sops.yaml   # Encrypted talosconfig
│       ├── kubeconfig.sops.yaml             # Encrypted kubeconfig
│       └── README.md                    # Documentation
└── IMPLEMENTATION.md                        # This file
```

## Security Considerations

1. **GitHub Token**: 1 month validity, short-lived, limited scope
2. **Client Certificates**: 1 year validity, balance of security and convenience
3. **Encryption**: All secrets encrypted with SOPS + age
4. **RBAC**: Principle of least privilege for CronJob
5. **Namespace Isolation**: Cert rotation in dedicated `cert-rotation` namespace
6. **No Plaintext**: Secrets never leave cluster/workstation unencrypted
7. **Cleanup**: Old secrets automatically cleaned from cluster (CronJob deletes workspace)
8. **Notifications**: Alerts sent on success/failure

## Monitoring

### Prometheus Metrics

The CronJob exports metrics to Prometheus AlertManager:

```
certificate_rotation_success_total
certificate_rotation_failure_total
certificate_rotation_duration_seconds
```

### Alerts

Check for these alerts in Prometheus:
- `certificate_rotation` severity=error
- `certificate_rotation` severity=warning

### Pushover Notifications

Webhook format for notifications:
```json
{
  "text": "🔄 Certificate Rotation: STATUS",
  "username": "SECRET_PUSHOVER_USER_KEY",
  "token": "SECRET_PUSHOVER_PROD_TOKEN"
}
```

## Troubleshooting

### Check Rotation Status

```bash
# View CronJob runs
kubectl get cronjobs -n cert-rotation

# View last rotation attempt
kubectl get pods -n cert-rotation -l job=cert-rotator

# View CronJob logs
kubectl logs -n cert-rotation job/cert-rotator-*

# Check recent commits
git log --oneline --grep "rotate" kubernetes/bootstrap/client-configs/
```

### Manual Decryption

```bash
# Decrypt talos config
sops -d -i kubernetes/bootstrap/client-configs/talos-client-config.sops.yaml > ~/.talos/config

# Decrypt kubeconfig
sops -d -i kubernetes/bootstrap/client-configs/kubeconfig.sops.yaml > ~/.kube/config

# Export environment variables
export TALOSCONFIG=~/.talos/config
export KUBECONFIG=~/.kube/config

# Verify access
talosctl version
kubectl get nodes
```

### Reset Rotation

If rotation fails and you need to reset:

```bash
# Delete failed job
kubectl delete job cert-rotator-* -n cert-rotation

# Re-run rotation
kubectl create job --from=cronjob/cert-rotator -n cert-rotation

# Or trigger from GitHub
gh workflow run "rotate-github-token.yaml"
```

## Customization

### Adding Multiple Roles

To add roles (e.g., readonly, backup):

1. Update `cert-rotator-config` ConfigMap:

```yaml
data:
  roles: "admin,readonly,backup"
```

2. The CronJob automatically generates certs for all roles specified.

### Changing Rotation Frequency

Edit `kubernetes/bootstrap/cert-rotation/cronjob.yaml`:

```yaml
spec:
  schedule: "0 2 1 * *"  # Monthly
  # OR
  schedule: "0 2 1 */3 *"  # Quarterly
  # OR
  schedule: "0 2 1 */6 *"  # Biannual
```

### Namespace Cleanup

To enable automatic cleanup after successful rotation:

```yaml
# Update configmaps.yaml
data:
  rotation-namespace-cleanup: "true"
```

This will delete the `cert-rotation` namespace after successful rotation.

## Integration with Flux

The secrets are stored in `flux-system` namespace. Flux will:

1. Decrypt secrets using age private key
2. Apply secrets to cluster
3. Reconcile changes automatically
4. Operators can use decrypted secrets

No manual intervention required after initial setup.

## Dependencies

- **Talos**: v1.10.5 or later (for `talosctl config new`)
- **Kubernetes**: v1.23.4 or later
- **Flux**: v2.x or later
- **SOPS**: v3.8.1 or later
- **Age**: v1.1.1 or later

## License

MIT License - See individual files for details.
