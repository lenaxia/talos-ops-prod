# Traefik v2 Compatibility Mode - Detailed Explanation

**Date:** 2025-11-10  
**Purpose:** Explain why v2 compatibility mode is critical for safe Traefik v3 upgrades

## What is v2 Compatibility Mode?

Traefik v2 compatibility mode is a feature in Traefik v3 that allows it to interpret routing rules using the old v2 syntax, preventing immediate breakage when upgrading from v2 to v3.

**Configuration:**
```yaml
core:
  defaultRuleSyntax: v2
```

## The Problem It Solves

### Breaking Change in v3

Traefik v3 introduced a **new rule matcher syntax** that's incompatible with v2. Without compatibility mode, upgrading would immediately break ALL routing rules.

### Syntax Differences

#### Multiple Path Prefixes

**v2 Syntax (Current):**
```yaml
rule: "PathPrefix(`/api`, `/admin`)"
```

**v3 Syntax (New):**
```yaml
rule: "PathPrefix(`/api`) || PathPrefix(`/admin`)"
```

#### Host with Multiple Paths

**v2 Syntax:**
```yaml
rule: "Host(`example.com`) && PathPrefix(`/api`, `/admin`)"
```

**v3 Syntax:**
```yaml
rule: "Host(`example.com`) && (PathPrefix(`/api`) || PathPrefix(`/admin`))"
```

#### Headers Matching

**v2 Syntax:**
```yaml
rule: "Headers(`X-Custom-Header`, `value1`, `value2`)"
```

**v3 Syntax:**
```yaml
rule: "Header(`X-Custom-Header`, `value1`) || Header(`X-Custom-Header`, `value2`)"
```

## Impact on Your Setup

### Current State
You have **144+ references** to Authelia across your ingress configurations, each using Traefik routing rules:

```yaml
# Example from your configs
annotations:
  traefik.ingress.kubernetes.io/router.middlewares: networking-chain-authelia@kubernetescrd
  traefik.ingress.kubernetes.io/router.entrypoints: websecure
```

### Without Compatibility Mode

**Immediate Impact:**
- ❌ All 144+ routes would need manual updates BEFORE upgrade
- ❌ High risk of breaking production services
- ❌ Significant downtime while fixing all routes
- ❌ No way to test incrementally
- ❌ All-or-nothing upgrade approach

**Example Breakage:**
```yaml
# This v2 rule would FAIL in v3 without compatibility mode
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
spec:
  routes:
    - match: PathPrefix(`/api`, `/admin`)  # ❌ BREAKS in v3
      kind: Rule
```

### With Compatibility Mode

**Immediate Impact:**
- ✅ All existing routes work unchanged
- ✅ Zero downtime during upgrade
- ✅ Gradual migration possible
- ✅ Test each route individually
- ✅ Phased rollout approach

**Same Example:**
```yaml
# With compatibility mode, this v2 rule WORKS in v3
core:
  defaultRuleSyntax: v2  # ← Enables v2 syntax

apiVersion: traefik.io/v1alpha1
kind: IngressRoute
spec:
  routes:
    - match: PathPrefix(`/api`, `/admin`)  # ✅ WORKS with compatibility
      kind: Rule
```

## How It Works

### Global Default

When you set `core.defaultRuleSyntax: v2`:
- ALL routers without explicit syntax use v2
- Traefik v3 interprets rules using v2 parser
- Existing configurations work unchanged

### Per-Router Override

You can override the default per-router for gradual migration:

```yaml
# Docker labels
labels:
  - "traefik.http.routers.test.ruleSyntax=v3"

# Kubernetes IngressRoute
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
spec:
  routes:
    - match: PathPrefix(`/api`) || PathPrefix(`/admin`)
      syntax: v3  # ← This route uses v3 syntax
      kind: Rule

# File configuration
http:
  routers:
    test:
      ruleSyntax: v3
```

This allows **heterogeneous configurations** where some routes use v2 and others use v3.

## Migration Strategy

### Phase 1: Enable Compatibility (Day 1)
```yaml
# Add to static configuration
core:
  defaultRuleSyntax: v2
```

**Result:**
- Upgrade to Traefik v3 completed
- All routes continue working
- No changes needed yet

### Phase 2: Gradual Migration (Weeks 1-4)

**Week 1:** Migrate non-critical routes
```yaml
# Test with low-traffic routes first
- match: PathPrefix(`/test`)
  syntax: v3
```

**Week 2:** Migrate medium-priority routes
```yaml
# Move to higher-traffic routes
- match: Host(`app.example.com`) && PathPrefix(`/api`)
  syntax: v3
```

**Week 3:** Migrate critical routes
```yaml
# Finally migrate production routes
- match: Host(`prod.example.com`)
  syntax: v3
```

**Week 4:** Validation
- Verify all routes migrated
- Test all applications
- Monitor for issues

### Phase 3: Remove Compatibility (After all migrated)
```yaml
# Remove from configuration
# core:
#   defaultRuleSyntax: v2  # ← DELETE THIS
```

**Result:**
- All routes now use v3 syntax
- Full v3 functionality available
- No compatibility overhead

## Your Specific Use Case

### Current Middleware Configuration

[`kubernetes/apps/networking/traefik/middlewares/middlewares.yaml`](../kubernetes/apps/networking/traefik/middlewares/middlewares.yaml):
```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: middlewares-authelia
spec:
  forwardAuth:
    address: http://authelia/api/verify?rd=https://authelia.${SECRET_DEV_DOMAIN}
```

This middleware is referenced in 144+ places. With compatibility mode:
1. ✅ All references continue working
2. ✅ You can update the endpoint to `/api/authz/forward-auth` separately
3. ✅ No need to touch all 144+ references immediately

### Example Application

[`kubernetes/apps/media/komga/app/helm-release.yaml`](../kubernetes/apps/media/komga/app/helm-release.yaml):
```yaml
annotations:
  traefik.ingress.kubernetes.io/router.middlewares: networking-chain-authelia@kubernetescrd
```

With compatibility mode:
- ✅ This annotation works unchanged in v3
- ✅ The middleware chain continues functioning
- ✅ No immediate updates required

## Performance Impact

### Compatibility Mode Overhead

**Minimal:** The v2 parser is still included in v3, so there's negligible performance impact.

**Recommendation:** Keep compatibility mode enabled until all routes are migrated, then remove it for a slight performance improvement.

## When to Remove Compatibility Mode

Remove compatibility mode when:
- ✅ All IngressRoutes migrated to v3 syntax
- ✅ All Ingress annotations updated
- ✅ All middleware rules updated
- ✅ All file-based configurations updated
- ✅ Thorough testing completed
- ✅ Monitoring confirms no issues

## Alternative Approach (Not Recommended)

**Without Compatibility Mode:**
1. Audit all 144+ routing rules
2. Update all to v3 syntax
3. Test all changes
4. Deploy all at once
5. Hope nothing breaks

**Risk:** HIGH - One mistake breaks multiple services

**With Compatibility Mode:**
1. Enable compatibility
2. Upgrade to v3
3. Migrate routes gradually
4. Test each change
5. Remove compatibility when done

**Risk:** LOW - Incremental changes, easy rollback

## Conclusion

**v2 compatibility mode is essential** for safe Traefik v3 upgrades. It:
- Prevents immediate breakage
- Allows gradual migration
- Reduces risk significantly
- Enables testing per-route
- Provides rollback capability

**For your setup with 144+ Authelia-protected routes, compatibility mode is not optional - it's critical for a successful upgrade.**