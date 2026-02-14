# Vendored CRDs

This directory contains vendored Custom Resource Definitions (CRDs) for Node Feature Discovery.

## Why CRDs are Vendored

The CRDs in this directory are vendored (downloaded and committed to this repository) rather than referencing them from remote GitHub URLs in the Kustomization. This is necessary because:

1. **CI/CD Compatibility**: GitHub Actions and other CI environments use shallow git checkouts (e.g., `fetch-depth: 1`), which prevent Kustomize from fetching remote GitHub references.

2. **Reliability**: Remote references introduce network dependency and can fail due to:
   - Network issues
   - Rate limiting
   - Repository unavailability
   - Authentication requirements

3. **Version Pinning**: Vendoring ensures exact version control and prevents unexpected changes from upstream updates.

4. **Self-Contained Repository**: This makes the repository fully self-contained and reproducible.

## Version Information

- **Source**: https://github.com/kubernetes-sigs/node-feature-discovery
- **Version**: v0.18.3
- **Original Path**: deployment/base/nfd-crds/nfd-api-crds.yaml
- **Download Date**: 2026-02-14

## Updating CRDs

When updating Node Feature Discovery to a new version:

1. Download the new CRDs from upstream:
   ```bash
   curl -o crds/nfd-api-crds.yaml https://raw.githubusercontent.com/kubernetes-sigs/node-feature-discovery/vX.Y.Z/deployment/base/nfd-crds/nfd-api-crds.yaml
   ```

2. Update the version in the HelmRelease (`helm-release.yaml`):
   ```yaml
   spec:
     chart:
       spec:
         version: X.Y.Z
   ```

3. Update this README with the new version information.

4. Commit the changes and create a PR for review.

## Validation

To validate that the CRDs are correctly formatted:

```bash
kubectl apply --dry-run=server -f crds/nfd-api-crds.yaml
```

Or use kubeconform:

```bash
kubeconform -strict crds/nfd-api-crds.yaml
```
