# Node Feature Discovery CRDs

These CRDs are vendored from the upstream kubernetes-sigs/node-feature-discovery repository.

## Source
- Repository: https://github.com/kubernetes-sigs/node-feature-discovery
- Version: v0.18.3
- Original path: deployment/base/nfd-crds/

## Updating CRDs

When updating node-feature-discovery, update these CRDs to match the new version:

1. Check the current version in helm-release.yaml
2. Download the CRDs from the matching upstream version:
   ```bash
   curl -O https://raw.githubusercontent.com/kubernetes-sigs/node-feature-discovery/vX.Y.Z/deployment/base/nfd-crds/nfd-api-crds.yaml
   ```
3. Replace the contents of nfd-api-crds.yaml
4. Update the version in this README

## CRD Files
- nfd-api-crds.yaml: Contains the NodeFeature, NodeFeatureGroup, and NodeFeatureRule CRDs
