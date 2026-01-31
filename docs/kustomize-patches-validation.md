# Kustomize Patches Validation

This script validates that all Kustomize files use the correct patches syntax to prevent
runtime errors with newer versions of kustomize.

## Problem

Older versions of Kustomize accepted string-based patches:

```yaml
patches:
  - ./my-patch.yaml
```

Newer versions of Kustomize (v4+) require object-based syntax:

```yaml
patches:
  - path: ./my-patch.yaml
```

Using the deprecated string syntax causes this error:

```
Error: invalid Kustomization: json: cannot unmarshal string into Go struct field Kustomization.patches of type types.Patch
```

## Usage

### As a pre-commit hook

```bash
# Install the pre-commit hook
./scripts/install-hooks.sh

# Or manually:
ln -s ../../scripts/validate-kustomize-patches.sh .git/hooks/pre-commit
```

### Manual validation

```bash
# Validate all kustomizations
bash scripts/validate-kustomize-patches.sh

# Validate specific directory
bash scripts/validate-kustomize-patches.sh ./kubernetes/apps
```

### In CI/CD

The validation is automatically run in:
- GitHub Actions: `.github/workflows/kubeconform.yaml`
- Local development: `task kubernetes:kubeconform`

## Migration Guide

To migrate from string-based to object-based patches:

### Simple patches

**Before:**
```yaml
patches:
  - ./my-patch.yaml
  - patches/config-patch.yaml
```

**After:**
```yaml
patches:
  - path: ./my-patch.yaml
  - path: patches/config-patch.yaml
```

### Patches with targets (no change needed)

```yaml
patches:
  - path: patches/config-patch.yaml
    target:
      kind: Deployment
      name: my-app
```

### Inline patches (no change needed)

```yaml
patches:
  - patch: |-
      apiVersion: v1
      kind: ConfigMap
      metadata:
        name: my-config
```

## Technical Details

The validation script:
1. Scans all `kustomization.yaml` files in the specified directory
2. Parses each file as YAML
3. Checks the `patches` field for string values (deprecated)
4. Reports errors with clear guidance on how to fix them
5. Returns non-zero exit code on any errors

## Related

- Kustomize Documentation: https://kustomize.io/
- Patches Reference: https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/patches/