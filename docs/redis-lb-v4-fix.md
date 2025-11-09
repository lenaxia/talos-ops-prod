# Redis-LB App-Template v4 Fix

## Date
2025-11-09

## Summary
Fixed validation errors in redis-lb helm-release.yaml after the automated v2→v3→v4 upgrade. The automated upgrade script missed several schema changes that required manual correction.

## Issues Found

### 1. Ingress Service Port Type Error
**Error**: `got string, want integer`

**Location**: `spec.values.ingress.main.hosts[0].paths[0].service.port`

**Problem**: Port was specified as string `"http"` instead of integer `8080`

**Root Cause**: The automated upgrade script preserved the port name reference from v2/v3, but v4 requires the actual integer port number.

### 2. Ingress Service Name Property
**Error**: `additional properties 'name' not allowed`

**Location**: `spec.values.ingress.main.hosts[0].paths[0].service`

**Problem**: Used `service.name` (v2 format) instead of `service.identifier` (v3+ format)

**Root Cause**: The automated upgrade script failed to transform this v2→v3 breaking change in the ingress service reference.

### 3. Persistence Structure Issues
**Error**: Multiple validation failures with `enabled` and `readOnly` properties

**Location**: `spec.values.persistence.config`

**Problems**:
- `enabled: true` is not needed in v4 (presence implies enabled)
- `readOnly: true` was at wrong level (should be inside `globalMounts`)

**Root Cause**: The automated upgrade script didn't properly restructure the persistence configuration for v4's schema changes.

## Fixes Applied

### Ingress Service (Lines 75-91)
```yaml
# BEFORE (v2 remnants)
ingress:
  main:
    enabled: true
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt-production
    hosts:
      - host: &uri redis-lb.${SECRET_DEV_DOMAIN}
        paths:
          - path: /
            pathType: Prefix
            service:
              name: main        # ❌ Wrong property name
              port: http        # ❌ String instead of integer
    tls:
      - hosts:
          - *uri
        secretName: *uri
    className: traefik

# AFTER (v4 compliant)
ingress:
  main:
    enabled: true
    className: traefik          # ✅ Moved up for clarity
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt-production
    hosts:
      - host: &uri redis-lb.${SECRET_DEV_DOMAIN}
        paths:
          - path: /
            pathType: Prefix
            service:
              identifier: main  # ✅ Correct v3+ property
              port: 8080        # ✅ Integer port number
    tls:
      - hosts:
          - *uri
        secretName: *uri
```

### Persistence Configuration (Lines 94-102)
```yaml
# BEFORE (v2/v3 structure)
persistence:
  config:
    enabled: true           # ❌ Not needed in v4
    type: configMap
    name: redis-lb-configmap
    readOnly: true          # ❌ Wrong level
    globalMounts:
      - path: /usr/local/etc/haproxy/haproxy.cfg
        subPath: haproxy.cfg

# AFTER (v4 structure)
persistence:
  config:
    type: configMap
    name: redis-lb-configmap
    globalMounts:
      - path: /usr/local/etc/haproxy/haproxy.cfg
        subPath: haproxy.cfg
        readOnly: true      # ✅ Moved to globalMounts level
```

## Why the Automated Upgrade Missed These

1. **Port Reference Complexity**: The script preserved port name references (`http`) without resolving them to actual port numbers. This worked in v2/v3 but v4 requires explicit integers.

2. **Incomplete v2→v3 Transformation**: The `service.name` → `service.identifier` change is a v2→v3 migration, but the automated script didn't catch it when upgrading from v2→v4.

3. **Persistence Schema Evolution**: The persistence schema changed significantly in v4, moving mount-specific properties like `readOnly` into the `globalMounts` array. The script didn't fully restructure this.

4. **Property Removal**: The `enabled` property was removed from persistence in v4 (presence implies enabled), but the script didn't remove it.

## Validation

After fixes, the file validates correctly:
```bash
✓ Valid YAML syntax
✓ Ingress service uses identifier (not name)
✓ Ingress service port is integer (8080)
✓ Persistence has no enabled property
✓ Persistence readOnly is in globalMounts
```

## Lessons Learned

### For Future Upgrades

1. **Port References**: Always resolve port name references to actual integers when upgrading to v4
   - Search for: `port: [a-z-]+` in ingress paths
   - Replace with actual port number from service definition

2. **Service References**: Check all ingress service references
   - v2 uses: `service.name`
   - v3+ uses: `service.identifier`

3. **Persistence Structure**: Verify persistence mount properties
   - v2/v3: `readOnly` at persistence level
   - v4: `readOnly` in `globalMounts` array
   - v4: Remove `enabled` property

4. **Multi-Version Jumps**: When jumping multiple versions (v2→v4), ensure all intermediate breaking changes are applied
   - v2→v3 changes (like service.name → service.identifier)
   - v3→v4 changes (like port type requirements)

### Script Improvements Needed

The automated upgrade script should be enhanced to:

1. Resolve port name references to integers in ingress paths
2. Transform `service.name` to `service.identifier` in ingress
3. Restructure persistence configuration for v4 schema
4. Remove deprecated properties like `persistence.*.enabled`
5. Validate against the actual v4 schema after transformation

## References

- [App-Template v4 Schema](https://github.com/bjw-s/helm-charts/tree/main/charts/library/common)
- [App-Template v3→v4 Migration Guide](https://github.com/bjw-s/helm-charts/blob/main/charts/library/common/docs/MIGRATION.md)
- Commit: d5d1687 - "fix(redis-lb): correct app-template v4 schema violations"