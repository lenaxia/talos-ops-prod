# Kustomize v5+ Patches Syntax Fix

## Problem
When kustomize was updated to v5.x+, the `patches` field syntax became stricter. 
The old syntax that accepted simple file paths now requires explicit `path:` or `patch:` keys.

## Error
```
Error: invalid Kustomization: json: cannot unmarshal string into Go struct field Kustomization.patches of type types.Patch
```

## Solution
Updated affected kustomization files to use proper `path:` key for patches:

### Files Changed

#### 1. kubernetes/apps/monitoring/vector/aggregator/kustomization.yaml
```yaml
patches:
  - path: ./patches/geoip.yaml  # was: - ./patches/geoip.yaml
```

#### 2. kubernetes/apps/home/hajimari/public/kustomization.yaml
```yaml
patches:
  - path: helm-release.yaml  # was: - helm-release.yaml
```

#### 3. kubernetes/apps/home/gamevault/app/kustomization.yaml
```yaml
patches:
  - path: patches/patch-postgres.yaml  # was: - patches/patch-postgres.yaml
```

## Why This is a Systematic Fix

1. **Prevents similar failures**: Other files in the repo already use correct syntax, but these three were missed
2. **Kustomize v5 compatibility**: Ensures all kustomization files work with kustomize v5.x+
3. **Minimal change**: Only updates syntax, no functional changes
4. **Future-proof**: Follows kustomize best practices for patch definitions

## References
- kustomize v5 migration guide
- Related to kube-prometheus-stack v81.4.2 update (Renovate PR #614)
