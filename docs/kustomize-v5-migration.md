# Kustomize v5.x Migration Guide

## Issue

Kustomize v5.x (released in Homebrew) requires structured patch syntax, while older versions accepted string-based syntax. This causes failures in the Kubeconform workflow with the error:

```
Error: invalid Kustomization: json: cannot unmarshal string into Go struct field Kustomization.patches of type types.Patch
```

## Old vs New Syntax

### Old Syntax (Deprecated - Kustomize v4.x)
```yaml
patches:
  - ./patches/geoip.yaml
  - patches/patch-postgres.yaml
```

### New Syntax (Required - Kustomize v5.x)
```yaml
patches:
  - path: ./patches/geoip.yaml
  - path: patches/patch-postgres.yaml
```

When using targets, ensure consistent indentation:
```yaml
patches:
  - path: patches/patch-postgres.yaml
    target:
      group: helm.toolkit.fluxcd.io
      kind: HelmRelease
      name: babybuddy
      version: v2
```

## Migration Status

All kustomization files in the repository have been migrated to Kustomize v5.x syntax:

- ✅ kubernetes/apps/monitoring/vector/aggregator/kustomization.yaml
- ✅ kubernetes/apps/storage/paperless/app/kustomization.yaml
- ✅ kubernetes/apps/media/outline/app/kustomization.yaml
- ✅ kubernetes/apps/home/hajimari/public/kustomization.yaml
- ✅ kubernetes/apps/home/gamevault/app/kustomization.yaml
- ✅ kubernetes/apps/home/babybuddy/base/kustomization.yaml
- ✅ kubernetes/apps/home/babybuddy/app/kustomization.yaml
- ✅ kubernetes/apps/home/babybuddy-pandaria/app/kustomization.yaml

## Prevention

To prevent future occurrences:

1. **Use the migration script**: `scripts/migrate-kustomize-patches.sh`
2. **Add pre-commit hook**: See `.git/hooks/pre-commit.sample`
3. **Test changes locally**: Run `kustomize build <directory>` before committing

## Resources

- [Kustomize v5.0.0 Release Notes](https://github.com/kubernetes-sigs/kustomize/releases/tag/kustomize%2Fv5.0.0)
- [Kustomize Patches Documentation](https://kubectl.docs.kubernetes.io/references/kustomize/builtins/#_patches_)
