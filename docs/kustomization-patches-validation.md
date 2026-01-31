# Kustomization Patches Format Validation

## Problem

The Kubeconform workflow failed with the following error:

```
Error: invalid Kustomization: json: cannot unmarshal string into Go struct field Kustomization.patches of type types.Patch
```

This error occurred in `./kubernetes/apps/monitoring/vector/aggregator/kustomization.yaml` when running `kustomize build`.

## Root Cause

The issue was caused by using an outdated Kustomization patches format. In older versions of Kustomize (prior to v5.0), patches could be specified as simple string paths:

```yaml
patches:
  - ./patches/geoip.yaml
```

However, starting with Kustomize v5.0, the patches format changed to require explicit object notation:

```yaml
patches:
  - path: ./patches/geoip.yaml
    target:
      kind: HelmRelease
      name: vector-aggregator
```

The new format requires:
- `path`: The path to the patch file
- `target`: An object specifying which resources to patch
  - `kind`: The Kubernetes resource kind (e.g., HelmRelease, Deployment)
  - `name`: The resource name
  - `version` (optional): The API version
  - `group` (optional): The API group

## Files Affected

The following files were using the old patches format and needed to be updated:

1. `kubernetes/apps/monitoring/vector/aggregator/kustomization.yaml`
2. `kubernetes/apps/home/hajimari/public/kustomization.yaml`
3. `kubernetes/apps/home/gamevault/app/kustomization.yaml`

## Solution

### 1. Fixed Kustomization Files

Updated all affected kustomization files to use the correct format:

```yaml
patches:
  - path: ./patches/geoip.yaml
    target:
      kind: HelmRelease
      name: vector-aggregator
```

### 2. Added Validation Step

Updated the Kubeconform workflow to validate patches format before running kustomize build:

```yaml
- name: Validate Kustomization Patches Format
  shell: bash
  run: |
    # Validation script that checks patches format
```

This validation uses `yq` to parse kustomization files and ensure patches use the correct object format.

### 3. Pre-commit Hook Script

Created `scripts/validate-kustomization-patches.sh` that can be used as a pre-commit hook to catch these issues before they're committed.

## Prevention

### Automated Prevention

1. **Workflow Validation**: The Kubeconform workflow now validates patches format before attempting to build kustomizations, providing early feedback.

2. **Pre-commit Hook**: Use the provided script as a pre-commit hook to catch issues locally:
   ```bash
   ln -s ../../scripts/validate-kustomization-patches.sh .git/hooks/pre-commit
   ```

### Best Practices

1. **Always use the target selector**: Even if a patch applies to all resources, use the target selector for clarity and future compatibility.

2. **Document patch targets**: Add comments explaining what resources the patch applies to and why.

3. **Test patches locally**: Run `kustomize build` locally before committing changes.

4. **Keep tools updated**: Ensure you're using a consistent version of kustomize across development and CI/CD.

## Migration Guide

If you encounter this error, follow these steps:

1. Identify the file with the old format (from the error message)
2. Update the patches section to use object notation
3. Add the `target` selector with at least `kind` and `name`
4. Test with `kustomize build <path>`
5. Commit and push

## References

- [Kustomize Patches Documentation](https://kubectl.docs.kubernetes.io/references/kustomize/glossary/#patches)
- [Kustomize v5.0 Release Notes](https://github.com/kubernetes-sigs/kustomize/releases/tag/kustomize%2Fv5.0.0)
