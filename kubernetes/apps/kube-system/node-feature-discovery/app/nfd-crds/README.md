# This directory contains vendored CRDs for node-feature-discovery.
# The CRDs are sourced from:
# https://github.com/kubernetes-sigs/node-feature-discovery/tree/v0.18.3/deployment/base/nfd-crds
#
# CRDs are vendored locally instead of using Kustomize's remote URL syntax
# (e.g., github.com/kubernetes-sigs/node-feature-discovery//deployment/base/nfd-crds?ref=v0.18.3)
# because flux-local cannot fetch remote GitHub resources during workflow execution.
# This ensures the Flux Diff workflow works correctly.
#
# To update CRDs:
# 1. Visit https://github.com/kubernetes-sigs/node-feature-discovery/releases
# 2. Find the matching version from ../../app/helm-release.yaml
# 3. Download CRDs from: https://raw.githubusercontent.com/kubernetes-sigs/node-feature-discovery/v<version>/deployment/base/nfd-crds/nfd-crds.yaml
# 4. Update this directory with new CRD content
