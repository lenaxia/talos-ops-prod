# HelmRelease Common Pitfalls

## Common Schema Validation Errors

### upgrade.strategy vs upgrade.remediation.strategy

The Flux HelmRelease v2 schema distinguishes between two different `strategy` fields:

#### upgrade.strategy (Incorrect for simple rollback)

According to the Flux HelmRelease v2 CRD:
- Type: `HelmUpgradeStrategy` (object)
- Used for advanced upgrade strategy configuration
- Should be an object with a `type` field

**Incorrect:**
```yaml
  upgrade:
    strategy: rollback  # This will fail kubeconform validation
```

**Correct (if you need upgrade strategy):**
```yaml
  upgrade:
    strategy:
      type: RollingUpdate  # or other strategy type
```

#### upgrade.remediation.strategy (Correct for rollback)

- Type: `string` (enum: `["", "Rollback"]`)
- Used for remediation strategy when an upgrade fails
- Should be a string value

**Correct pattern for rollback on failure:**
```yaml
  upgrade:
    cleanupOnFail: true
    remediation:
      retries: 5
      strategy: rollback  # Correct: nested under remediation
```

## Example

### Before (Incorrect - causes kubeconform validation failure):
```yaml
  upgrade:
    cleanupOnFail: true
    remediation:
      retries: 5
    strategy: rollback  # <-- WRONG: directly under upgrade
```

### After (Correct):
```yaml
  upgrade:
    cleanupOnFail: true
    remediation:
      retries: 5
      strategy: rollback  # <-- CORRECT: nested under remediation
```

## Reference

- Flux HelmRelease v2 API: https://fluxcd.io/flux/components/helm/helmreleases/
- Schema: https://kubernetes-schemas.pages.dev/helm.toolkit.fluxcd.io/helmrelease_v2.json
