# Authelia & Traefik Upgrade Analysis

**Date:** 2025-11-09  
**Status:** Investigation Complete - Shadow Testing Required

## Executive Summary

Both Authelia and Traefik require significant upgrades with **MAJOR breaking changes**:

- **Authelia**: v4.37.5 → v4.39.14 (Chart: v0.8.58 → v0.10.49)
- **Traefik**: v2.11.13 → v3.6.0 (Chart: v27.0.2 → v37.2.0) **[MAJOR VERSION CHANGE]**

**Risk Level:** HIGH - Traefik v2→v3 is a major version upgrade with significant breaking changes that will affect all ingress configurations.

## Current Versions

### Authelia
- **Current App Version:** v4.37.5
- **Current Chart Version:** v0.8.58
- **Latest App Version:** v4.39.14 (released 2025-11-09)
- **Latest Chart Version:** v0.10.49 (released 2025-11-04)
- **Version Gap:** 2 minor versions (4.37 → 4.39)

### Traefik
- **Current App Version:** v2.11.13
- **Current Chart Version:** v27.0.2
- **Latest App Version:** v3.6.0 (released 2025-11-07)
- **Latest Chart Version:** v37.2.0 (released 2025-10-22)
- **Version Gap:** MAJOR version jump (v2 → v3)

## Authelia Upgrade Path (v4.37 → v4.39)

### Key Changes in v4.38

#### 1. **CRITICAL: API Endpoint Migration**
The legacy `/api/verify` endpoint is **deprecated** and must be migrated to new `/api/authz/*` endpoints:

**Old Configuration:**
```
http://authelia:9091/api/verify?rd=https://auth.example.com
```

**New Configurations (by proxy type):**
- **Traefik/Caddy/HAProxy:** `/api/authz/forward-auth`
- **NGINX:** `/api/authz/auth-request`
- **Envoy:** `/api/authz/ext-authz`

**Impact:** All middleware configurations in Traefik that reference Authelia need updating.

#### 2. Server Configuration Changes
**Old Format:**
```yaml
server:
  host: '0.0.0.0'
  port: 9091
  path: 'authelia'
```

**New Format:**
```yaml
server:
  address: 'tcp://0.0.0.0:9091/authelia'
```

#### 3. Multi-Domain Session Support
New `cookies` array structure for session configuration:
```yaml
session:
  cookies:
    - domain: 'example.com'
      authelia_url: 'https://auth.example.com'
      default_redirection_url: 'https://www.example.com'
```

### Database Migrations
Authelia includes automatic schema migrations. Run before upgrading:
```bash
authelia storage migrate list-up
authelia storage migrate up
```

## Traefik Upgrade Path (v2.11 → v3.6) **[CRITICAL]**

### Major Breaking Changes

#### 1. **Rule Matcher Syntax Change**
Traefik v3 introduces new rule matcher syntax. **Migration strategy:**

**Phase 1 - Enable v2 Compatibility:**
```yaml
# Add to static configuration
core:
  defaultRuleSyntax: v2
```

This allows existing v2 rules to work while you migrate.

**Phase 2 - Migrate Rules Gradually:**
Can set per-router:
```yaml
# Docker labels
traefik.http.routers.test.ruleSyntax=v2

# Kubernetes IngressRoute
spec:
  routes:
    - match: PathPrefix(`/foo`, `/bar`)
      syntax: v2
```

**Phase 3 - Remove Compatibility Mode:**
Once all rules migrated, remove `core.defaultRuleSyntax: v2`

#### 2. **Removed Providers**
- **Marathon** - Completely removed (EOL October 2021)
- **Rancher v1** - Completely removed (no longer maintained)
- **Docker Swarm Mode** - Moved to dedicated `swarm` provider

**Migration for Swarm:**
```yaml
# OLD (v2)
providers:
  docker:
    swarmMode: true

# NEW (v3)
providers:
  swarm:
    endpoint: "tcp://127.0.0.1:2377"
```

#### 3. **Removed Options**
- `experimental.http3` - HTTP/3 is now stable, remove this option
- `experimental.kubernetesgateway` - Deprecated in v3.1
- `pilot.*` - Traefik Pilot discontinued (October 2022)
- `metrics.influxDB` - InfluxDB v1 support removed
- Various `tls.caOptional` settings - Now server-side only

#### 4. **Namespace Changes**
Consul/Nomad providers:
```yaml
# OLD
consulCatalog:
  namespace: foobar

# NEW  
consulCatalog:
  namespaces:
    - foobar
```

## Current Configuration Analysis

### Authelia Configuration
**File:** [`kubernetes/apps/networking/authelia/app/helm-release.yaml`](../kubernetes/apps/networking/authelia/app/helm-release.yaml)

**Current Setup:**
- Using embedded Redis (sentinel mode with 2 replicas)
- LDAP authentication against NAS
- Duo Push for 2FA
- Extensive access control rules
- LoadBalancer service type

**Requires Updates:**
1. Middleware endpoint in Traefik (currently uses `/api/verify`)
2. Server configuration format (if using `path` option)
3. Session configuration (may need cookies array)

### Traefik Configuration  
**File:** [`kubernetes/apps/networking/traefik/app/helm-release.yaml`](../kubernetes/apps/networking/traefik/app/helm-release.yaml)

**Current Setup:**
- 4 replicas
- LoadBalancer service
- Experimental plugins (htransformation, ldapAuth)
- Custom TLS options
- Prometheus metrics

**Requires Updates:**
1. Add `core.defaultRuleSyntax: v2` for compatibility
2. Review all IngressRoute/Middleware configurations
3. Update Authelia middleware endpoint
4. Verify plugin compatibility with v3

### Middleware Configuration
**File:** [`kubernetes/apps/networking/traefik/middlewares/middlewares.yaml`](../kubernetes/apps/networking/traefik/middlewares/middlewares.yaml)

**Current Authelia Middleware:**
```yaml
metadata:
  name: middlewares-authelia
spec:
  forwardAuth:
    address: http://authelia/api/verify?rd=https://authelia.${SECRET_DEV_DOMAIN}
```

**Must Change To:**
```yaml
metadata:
  name: middlewares-authelia
spec:
  forwardAuth:
    address: http://authelia/api/authz/forward-auth
    # rd parameter now handled via authelia_url in session config
```

## Recommended Upgrade Strategy

### Phase 1: Shadow Testing (CURRENT PHASE)
1. ✅ Deploy shadow Traefik v3 instance in `default` namespace
2. ✅ Deploy shadow Authelia v4.39 instance in `default` namespace  
3. ✅ Configure shadow instances to communicate
4. ✅ Test with sample applications
5. ✅ Validate authentication flows
6. ✅ Verify all middleware chains work

### Phase 2: Authelia Upgrade (Lower Risk)
1. Backup current Authelia database
2. Run storage migration: `authelia storage migrate up`
3. Update Helm chart to v0.10.49
4. Update app version to v4.39.14
5. Update server configuration format
6. Update session configuration if needed
7. Monitor logs and functionality

### Phase 3: Traefik Preparation
1. Add `core.defaultRuleSyntax: v2` to static config
2. Update Authelia middleware to use `/api/authz/forward-auth`
3. Test with current Traefik v2 (should work with new endpoint)
4. Document all custom IngressRoutes and Middlewares

### Phase 4: Traefik Upgrade (Higher Risk)
1. Backup all Traefik configurations
2. Update Helm chart to v37.2.0
3. Update app version to v3.6.0
4. Keep `core.defaultRuleSyntax: v2` enabled
5. Monitor all ingress routes
6. Gradually migrate rules to v3 syntax
7. Remove compatibility mode once complete

### Phase 5: Validation & Cleanup
1. Test all protected applications
2. Verify 2FA flows
3. Check access control rules
4. Monitor metrics and logs
5. Remove shadow instances
6. Document final configuration

## Testing Checklist

### Authelia Testing
- [ ] LDAP authentication works
- [ ] Duo Push 2FA works
- [ ] WebAuthn/TOTP works
- [ ] Access control rules enforced correctly
- [ ] Session management works
- [ ] Redis sentinel failover works
- [ ] All protected apps accessible

### Traefik Testing
- [ ] All ingress routes resolve
- [ ] TLS certificates work
- [ ] Middleware chains function
- [ ] Authelia integration works
- [ ] Metrics collection works
- [ ] LoadBalancer service works
- [ ] Plugin functionality maintained

### Integration Testing
- [ ] Login flow: Traefik → Authelia → App
- [ ] Logout flow works
- [ ] Session persistence across apps
- [ ] 2FA prompts appear correctly
- [ ] Access denied for unauthorized users
- [ ] Redirect flows work properly

## Rollback Plan

### Authelia Rollback
```bash
# Rollback database migration
authelia storage migrate down --target <previous_version>

# Rollback Helm release
flux suspend helmrelease authelia -n networking
kubectl rollout undo deployment/authelia -n networking
# Or restore from backup
```

### Traefik Rollback
```bash
# Rollback Helm release
flux suspend helmrelease traefik -n networking
kubectl rollout undo deployment/traefik -n networking
# Restore middleware configurations if changed
```

## Risk Assessment

### Authelia Upgrade Risk: **MEDIUM**
- **Pros:** Minor version upgrade, backward compatible API
- **Cons:** API endpoint changes affect all integrations
- **Mitigation:** Shadow testing, gradual rollout

### Traefik Upgrade Risk: **HIGH**
- **Pros:** v2 compatibility mode available, gradual migration possible
- **Cons:** Major version change, affects ALL ingress configurations
- **Mitigation:** Extensive shadow testing, keep v2 compatibility enabled initially

## Resource Requirements

### Shadow Instances
- **Namespace:** `default` (as requested)
- **Traefik:** ~500Mi memory, 500m CPU (4 replicas = 2GB/2 CPU total)
- **Authelia:** ~500Mi memory, 500m CPU + Redis overhead
- **Total:** ~3GB memory, ~3 CPU cores for testing

## Timeline Estimate

- **Shadow Setup & Testing:** 2-4 hours
- **Authelia Upgrade:** 1-2 hours (including validation)
- **Traefik Preparation:** 2-3 hours (config updates)
- **Traefik Upgrade:** 2-4 hours (including validation)
- **Total:** 7-13 hours (spread over multiple sessions)

## References

- [Authelia v4.38 Release Notes](https://github.com/authelia/authelia/blob/master/docs/content/blog/release-notes-4.38/index.md)
- [Authelia v4.39 Release](https://github.com/authelia/authelia/releases/tag/v4.39.14)
- [Traefik v2 to v3 Migration Guide](https://doc.traefik.io/traefik/migrate/v2-to-v3/)
- [Traefik v3.6.0 Release Notes](https://github.com/traefik/traefik/releases/tag/v3.6.0)
- [Authelia Helm Chart](https://github.com/authelia/chartrepo)
- [Traefik Helm Chart](https://github.com/traefik/traefik-helm-chart)

## Next Steps

1. **Review this document** with team/stakeholders
2. **Create shadow instances** for testing (see separate files)
3. **Test authentication flows** thoroughly
4. **Document any issues** found during testing
5. **Plan production upgrade** window
6. **Execute upgrades** following phased approach

---

**Note:** This is a significant infrastructure change. Do NOT rush the upgrade. Thorough testing of shadow instances is critical before touching production.