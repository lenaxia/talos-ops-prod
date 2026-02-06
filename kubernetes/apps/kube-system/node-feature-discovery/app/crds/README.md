# Vendored CRDs

This directory contains vendored Kubernetes Custom Resource Definitions (CRDs).

## Why Vendoring?

Remote GitHub references in Kustomize resources (e.g., `github.com/kubernetes-sigs/node-feature-discovery//deployment/base/nfd-crds?ref=v0.18.3`) are not supported in CI environments that use shallow git checkouts (`fetch-depth: 1`).

## Management

When updating vendored CRDs:

1. Download latest version from upstream
2. Verify version matches what's being used
3. Commit changes

## Source

- `nfd-api-crds.yaml`: Vendored from [kubernetes-sigs/node-feature-discovery](https://github.com/kubernetes-sigs/node-feature-discovery) v0.18.3
  - Contains: NodeFeature, NodeFeatureGroup, NodeFeatureRule CRDs
