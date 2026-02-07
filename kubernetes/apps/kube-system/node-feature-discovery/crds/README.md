# Node Feature Discovery CRDs

This directory contains Custom Resource Definitions (CRDs) for Node Feature Discovery.

## Source

These CRDs are sourced from the upstream Node Feature Discovery repository:
- Repository: https://github.com/kubernetes-sigs/node-feature-discovery
- Version: v0.18.3
- Original Path: deployment/base/nfd-crds/nfd-api-crds.yaml

## Maintenance

When upgrading Node Feature Discovery to a new version, update the CRD files to match:

1. Visit the Node Feature Discovery releases: https://github.com/kubernetes-sigs/node-feature-discovery/releases
2. Note the new version tag
3. Download the updated CRD file: `https://raw.githubusercontent.com/kubernetes-sigs/node-feature-discovery/<version>/deployment/base/nfd-crds/nfd-api-crds.yaml`
4. Update the version comment at the top of `nfd-api-crds.yaml`
5. Test the changes locally to ensure compatibility

## Why Local CRDs?

These CRDs are stored locally in the repository rather than referencing them via GitHub URLs in kustomization because:

1. **CI/CD Reliability**: Remote GitHub URLs in kustomizations can fail in CI/CD environments when kustomize attempts to resolve them as file paths
2. **Version Tracking**: Storing CRDs locally allows explicit version tracking and easier rollback if needed
3. **Self-Contained Repository**: Makes the GitOps repository more self-contained and less dependent on external resources during validation
4. **Validation Consistency**: Ensures consistent behavior across different environments (local, CI, production)
