# Client Configs

This directory contains automatically rotated client configuration files for accessing your cluster.

## Files

- `talosconfig.sops.yaml`: Talos client configuration (self-rotating)
- `kubeconfig.sops.yaml`: Kubernetes client configuration (in-cluster rotation)

## Rotation

Both configs rotate monthly via the `cert-rotator` CronJob in `../cert-rotation/`.

### Talos Config Rotation (Self-Rotating)
The CronJob uses the current `talosconfig` to generate a new `talosconfig`:
- Month 1: Uses config-v1 → Generates config-v2
- Month 2: Uses config-v2 → Generates config-v3
- Continues indefinitely (always has ~11 months until expiry)

### Kubeconfig Rotation (In-Cluster)
The CronJob generates a new kubeconfig using Kubernetes CSR:
- Creates CSR with ServiceAccount permissions
- CSR auto-approved by `kubelet-csr-approver`
- New cert has 1 year validity

## Decryption

To decrypt a config for use:

```bash
# Decrypt and save to file
sops -d -i talos-client-config.sops.yaml > ~/.talos/config
sops -d -i kubeconfig.sops.yaml > ~/.kube/config

# Export environment
export TALOSCONFIG=~/.talos/config
export KUBECONFIG=~/.kube/config
```

## Certificate Validity

- Talosctl config: 1 year (8760 hours)
- Kubectl config: 1 year
- GitHub deploy token: 1 month

## Role-Based Access

The templates support configurable roles via the `cert-rotator-config` ConfigMap:
- **Admin**: Full admin access to Talos API and Kubernetes API
- **Read-only**: Limited permissions (default: admin, can be customized)

To add additional roles:
1. Update `cert-role` in `cert-rotator-config` ConfigMap
2. The CronJob will automatically generate certs for all roles specified

## Security Notes

- All configs are encrypted using SOPS + age
- Private keys never leave the cluster unencrypted
- Age public key: `age1rr569v9jm7ck70q4wpnspfhdvt4y5m6s604tx0ygs0a65qkt7g4qdszk6k`
- Configs are stored in `flux-system` namespace

## Rotation Process

1. GitHub Actions rotates deploy token (1st day of month)
2. Flux decrypts and applies updated GitHub token secret
3. CronJob runs (2 AM UTC on 1st of month)
4. CronJob generates new talosctl and kubectl configs (1 year validity)
5. CronJob commits both encrypted configs to gitops repo
6. Flux reconciles and applies new secrets
7. Operators retrieve latest configs when needed

## Troubleshooting

To check rotation status:
```bash
# Check last rotation
git log --oneline --grep "rotate" kubernetes/bootstrap/client-configs/ --max-count=1

# Check CronJob status
kubectl get cronjobs -n cert-rotation
kubectl get pods -n cert-rotation -l job=cert-rotator
kubectl logs -n cert-rotation job/cert-rotator-*
```

## Monitoring

The CronJob sends alerts on rotation success or failure via:
- Pushover webhooks (Slack/Discord)
- Prometheus AlertManager

Check these alerts if rotation fails:
```bash
# Prometheus alerts
kubectl get prometheus -n monitoring prometheus -o yaml | grep -A 5 "certificate-rotation"
```
