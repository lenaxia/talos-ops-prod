#!/usr/bin/env bash
set -o errexit
set -o pipefail

# Script to validate kustomization files use the new v4 patch syntax

echo "Checking for old-style Kustomize patch syntax..."

# Find all kustomization.yaml files
KUSTOMIZE_FILES=$(find /home/runner/work/talos-ops-prod/talos-ops-prod/kubernetes -type f -name "kustomization.yaml")

ERRORS_FOUND=0

for file in $KUSTOMIZE_FILES; do
    # Check if file contains patches section with old-style string format
    # Old format: patches: - ./path/to/patch.yaml
    # New format: patches: - path: ./path/to/patch.yaml
    if grep -A 2 "^patches:" "$file" | grep -qE "^\s+-\s+\./"; then
        echo "ERROR: Old-style patch syntax found in $file"
        grep -A 2 "^patches:" "$file" | grep -E "^\s+-\s+\./"
        ERRORS_FOUND=1
    fi
done

if [ $ERRORS_FOUND -eq 0 ]; then
    echo "✓ All kustomization files use the new v4 patch syntax"
    exit 0
else
    echo "✗ Found kustomization files with old-style patch syntax"
    exit 1
fi
