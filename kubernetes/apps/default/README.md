# Shadow Testing Environment

This directory contains shadow instances for testing major version upgrades before applying them to production.

**Namespace:** `default`

## Components

### 1. Authelia Shadow (v4.39.14)
- **Chart:** v0.10.49 (latest)
- **App:** v4.39.14 (latest)
- **Current Production:** v4.37.5 (chart v0.8.58)
- **Change:** Minor version upgrade with chart structure migration (v3 → v4)
- **Key Feature:** New v4 chart structure with updated secret management

**Files:**
- [`authelia-shadow/ks.yaml`](authelia-shadow/ks.yaml)
- [`authelia-shadow/app/helm-release.yaml`](authelia-shadow/app/helm-release.yaml)
- [`authelia-shadow/app/service.yaml`](authelia-shadow/app/service.yaml)
- [`authelia-shadow/app/ingress.yaml`](authelia-shadow/app/ingress.yaml)
- [`authelia-shadow/app/kustomization.yaml`](authelia-shadow/app/kustomization.yaml)

### 2. Echo Server Shadow (Test Application)
- **Purpose:** Validate authentication flow through shadow instances
- **Protected by:** Authelia Shadow

**Files:**
- [`echo-server-shadow/ks.yaml`](echo-server-shadow/ks.yaml)
- [`echo-server-shadow/app/helm-release.yaml`](echo-server-shadow/app/helm-release.yaml)
- [`echo-server-shadow/app/kustomization.yaml`](echo-server-shadow/app/kustomization.yaml)

> **Note:** A `traefik-shadow` instance previously lived in this directory for the
> v2→v3 chart upgrade test and has since been removed (production migrated to Traefik v3).

## Configuration Differences

### Authelia Shadow vs Production

| Feature | Production (v4.37) | Shadow (v4.39) |
|---------|-------------------|----------------|
| Chart Version | v0.8.58 (v3 structure) | v0.10.49 (v4 structure) |
| App Version | v4.37.5 | v4.39.14 |
| Service Type | LoadBalancer | ClusterIP |
| Chart Structure | Old v3 format | New v4 format |
| Secret Management | Flat structure | Nested per-component |
| Redis | Embedded (sentinel) | Embedded (sentinel) |
| Storage | SQLite | SQLite |
| LDAP | Enabled | Enabled |
| OIDC | Disabled in shadow | Disabled in shadow |

## Key Differences in Shadow Setup

### Simplified Configuration
The shadow instances use simplified configurations for testing:
- **No LoadBalancer:** Uses ClusterIP to avoid IP conflicts
- **Minimal replicas:** 1-2 replicas vs production's 4
- **Local domains:** Uses `.local` domains for testing
- **Filesystem notifier:** Instead of SMTP for simplicity
- **OIDC disabled:** Focus on basic auth flow first

### Security Notes
- Shadow instances use **insecure test secrets**
- LDAP password is hardcoded (same as production for testing)
- Not exposed externally
- Should be deleted after testing

## Testing Procedure

### 1. Deploy Shadow Instances

The shadow instances will be deployed automatically by Flux when you commit these files.

**Deployment Order:**
1. Authelia Shadow (depends on cert-manager)
2. Echo Server Shadow (depends on Authelia)

### 2. Verify Deployments

```bash
# Check Authelia Shadow
kubectl get pods -n default -l app.kubernetes.io/name=authelia
kubectl logs -n default -l app.kubernetes.io/instance=authelia-shadow

# Check Echo Server Shadow
kubectl get pods -n default -l app.kubernetes.io/name=echo-server-shadow
```

## Cleanup

Once testing is complete and you're ready to upgrade production:

```bash
# Delete shadow instances
kubectl delete kustomization cluster-default-authelia-shadow -n flux-system
kubectl delete kustomization cluster-default-echo-server-shadow -n flux-system

# Or delete the directories and commit
rm -rf kubernetes/apps/default/authelia-shadow
rm -rf kubernetes/apps/default/echo-server-shadow
```

## Known Issues & Limitations

### Authelia v4
1. **Chart Structure:** Complete rewrite from v3 to v4
2. **Secret Management:** New nested structure per component
3. **Duration Format:** Requires units ('1 hour' not '1h')
4. **Address Format:** Many services use full URIs now

## Migration Path to Production

### Authelia (Lower Risk)
1. Backup production Authelia database
2. Test database migration: `authelia storage migrate list-up`
3. Update production chart to v0.10.49 with new v4 structure
4. Monitor and validate

## References

- [Authelia Config Migration Guide](../../docs/authelia-config-migration-v3-to-v4.md)
- [Authelia v4.38 Release Notes](https://www.authelia.com/blog/release-notes-4.38/)