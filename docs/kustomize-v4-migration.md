# Kustomize v4 Patch Migration Guide

## Background

Kustomize 5.x (which we use in the e2e workflow) requires the **new v4 patch syntax**, while older versions supported both v3 and v4 formats. The v3 format used string-based patches, but this is no longer supported.

## The Change

### Old Format (v3) - No longer works
```yaml
patches:
  - ./patches/geoip.yaml
```

### New Format (v4) - Required
```yaml
patches:
  - path: ./patches/geoip.yaml
```

## Migration Steps

1. Find all kustomization files with the old syntax
2. Change `patches:` items from strings to objects
3. Use the `path:` key to specify the patch file location

## Example

### Before
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: monitoring
resources:
  - ./helm-release.yaml
patches:
  - ./patches/geoip.yaml
```

### After
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: monitoring
resources:
  - ./helm-release.yaml
patches:
  - path: ./patches/geoip.yaml
```

## Complex Patches

For patches with targets, ensure consistent indentation:

### Before
```yaml
patches:
- path: patches/patch-postgres.yaml
  target:
    group: helm.toolkit.fluxcd.io
    kind: HelmRelease
```

### After
```yaml
patches:
  - path: patches/patch-postgres.yaml
    target:
      group: helm.toolkit.fluxcd.io
      kind: HelmRelease
```

## Validation

Run the validation script to check for old syntax:
```bash
bash .github/scripts/validate-kustomize-syntax.sh
```

This script is automatically run as part of the e2e workflow.

## Related Resources

- [Kustomize v4 Migration Guide](https://kustomize.io/blog/2022/08/23/kustomize-v4/)
- [Kustomize Patches Documentation](https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/patches/)
