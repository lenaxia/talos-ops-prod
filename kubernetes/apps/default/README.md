# Shadow Testing Environment

This directory contains shadow instances of Authelia and Traefik for testing major version upgrades before applying them to production.

## Overview

**Purpose:** Validate Authelia v4.39 (chart v0.10.49) and Traefik v3.6 (chart v37.2.0) upgrades in isolation.

**Namespace:** `default`

## Components

### 1. Traefik Shadow (v3.6.0)
- **Chart:** v37.2.0 (latest)
- **App:** v3.6.0 (latest)
- **Current Production:** v2.11.13 (chart v27.0.2)
- **Change:** MAJOR version upgrade (v2 → v3)
- **Key Feature:** v2 compatibility mode enabled via `core.defaultRuleSyntax: v2`

**Files:**
- [`traefik-shadow/ks.yaml`](traefik-shadow/ks.yaml)
- [`traefik-shadow/app/helm-release.yaml`](traefik-shadow/app/helm-release.yaml)
- [`traefik-shadow/app/middlewares.yaml`](traefik-shadow/app/middlewares.yaml)
- [`traefik-shadow/app/kustomization.yaml`](traefik-shadow/app/kustomization.yaml)

### 2. Authelia Shadow (v4.39.14)
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

### 3. Echo Server Shadow (Test Application)
- **Purpose:** Validate authentication flow through shadow instances
- **Protected by:** Authelia Shadow via Traefik Shadow middleware chain

**Files:**
- [`echo-server-shadow/ks.yaml`](echo-server-shadow/ks.yaml)
- [`echo-server-shadow/app/helm-release.yaml`](echo-server-shadow/app/helm-release.yaml)
- [`echo-server-shadow/app/kustomization.yaml`](echo-server-shadow/app/kustomization.yaml)

## Configuration Differences

### Traefik Shadow vs Production

| Feature | Production (v2.11) | Shadow (v3.6) |
|---------|-------------------|---------------|
| Chart Version | v27.0.2 | v37.2.0 |
| App Version | v2.11.13 | v3.6.0 |
| Service Type | LoadBalancer | ClusterIP |
| Replicas | 4 | 2 |
| IngressClass | traefik (default) | traefik-shadow |
| Rule Syntax | v2 (implicit) | v2 (explicit via core.defaultRuleSyntax) |
| Ports | 80/443 | 8000/8443 |

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
1. Traefik Shadow (depends on cert-manager)
2. Authelia Shadow (depends on cert-manager)
3. Echo Server Shadow (depends on both above)

### 2. Verify Deployments

```bash
# Check Traefik Shadow
kubectl get pods -n default -l app.kubernetes.io/name=traefik-shadow
kubectl logs -n default -l app.kubernetes.io/name=traefik-shadow

# Check Authelia Shadow
kubectl get pods -n default -l app.kubernetes.io/name=authelia
kubectl logs -n default -l app.kubernetes.io/instance=authelia-shadow

# Check Echo Server Shadow
kubectl get pods -n default -l app.kubernetes.io/name=echo-server-shadow
```

### 3. Test Authentication Flow

```bash
# Port forward to test locally
kubectl port-forward -n default svc/traefik-shadow 8443:8443

# Add to /etc/hosts
echo "127.0.0.1 authelia-shadow.local echo-shadow.local" | sudo tee -a /etc/hosts

# Test endpoints
curl -k https://authelia-shadow.local:8443/api/health
curl -k https://echo-shadow.local:8443/
```

### 4. Validation Checklist

- [ ] Traefik Shadow pods running
- [ ] Authelia Shadow pods running
- [ ] Redis pods running (authelia-shadow-redis-*)
- [ ] Echo Server Shadow pod running
- [ ] Traefik v3 dashboard accessible
- [ ] Authelia health endpoint responds
- [ ] Echo server redirects to Authelia login
- [ ] LDAP authentication works
- [ ] Session persistence works
- [ ] Middleware chain functions correctly
- [ ] No errors in logs

### 5. Test Scenarios

#### Basic Authentication
1. Access echo-shadow.local
2. Should redirect to authelia-shadow.local
3. Login with LDAP credentials
4. Should redirect back to echo server
5. Verify session cookie set

#### Session Management
1. Close browser
2. Reopen and access echo-shadow.local
3. Should still be authenticated (if within session timeout)

#### Access Control
1. Test with different user groups
2. Verify policies enforced correctly

## Cleanup

Once testing is complete and you're ready to upgrade production:

```bash
# Delete shadow instances
kubectl delete kustomization cluster-default-traefik-shadow -n flux-system
kubectl delete kustomization cluster-default-authelia-shadow -n flux-system
kubectl delete kustomization cluster-default-echo-server-shadow -n flux-system

# Or delete the directories and commit
rm -rf kubernetes/apps/default/traefik-shadow
rm -rf kubernetes/apps/default/authelia-shadow
rm -rf kubernetes/apps/default/echo-server-shadow
```

## Known Issues & Limitations

### Traefik v3
1. **Rule Syntax:** Currently using v2 compatibility mode
2. **Plugins:** May need updates for v3 compatibility
3. **Metrics:** ServiceMonitor disabled in shadow

### Authelia v4
1. **Chart Structure:** Complete rewrite from v3 to v4
2. **Secret Management:** New nested structure per component
3. **Duration Format:** Requires units ('1 hour' not '1h')
4. **Address Format:** Many services use full URIs now

## Migration Path to Production

### Phase 1: Authelia (Lower Risk)
1. Backup production Authelia database
2. Test database migration: `authelia storage migrate list-up`
3. Update production chart to v0.10.49 with new v4 structure
4. Monitor and validate

### Phase 2: Traefik (Higher Risk)
1. Add `core.defaultRuleSyntax: v2` to production config
2. Update Authelia middleware to use `/api/authz/forward-auth`
3. Test with production Traefik v2 (should work)
4. Update production chart to v37.2.0
5. Keep v2 compatibility mode enabled
6. Gradually migrate rules to v3 syntax
7. Remove compatibility mode

## References

- [Main Upgrade Analysis](../../docs/authelia-traefik-upgrade-analysis.md)
- [Authelia Config Migration Guide](../../docs/authelia-config-migration-v3-to-v4.md)
- [Traefik v2→v3 Migration](https://doc.traefik.io/traefik/migrate/v2-to-v3/)
- [Authelia v4.38 Release Notes](https://www.authelia.com/blog/release-notes-4.38/)

## Support

For issues or questions about the shadow testing environment, refer to the documentation files listed above or check the Authelia/Traefik official documentation.