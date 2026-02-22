#!/usr/bin/env bash
set -o errexit
set -o pipefail

# This script validates Flux HelmRelease files for common configuration issues
# Specifically checking for invalid postRenderer configurations

KUBERNETES_DIR="${1:-kubernetes}"
FOUND_ISSUES=0

echo "=== Validating HelmRelease postRenderer configurations ==="

# Find all HelmRelease files
find "${KUBERNETES_DIR}" -type f -name "*.yaml" -o -name "*.yml" | while read -r file; do
    # Check if file is a HelmRelease
    if grep -q "kind: HelmRelease" "$file" 2>/dev/null; then
        # Check for invalid postRenderer key 'kustomize' (should be 'kustomization')
        if grep -q "postRenderers:" "$file" 2>/dev/null; then
            # Use awk to find the postRenderers section and check for 'kustomize' key
            if awk '/postRenderers:/{flag=1} flag && /^ +- kustomize:/{print FILENAME": Invalid postRenderer key 'kustomize' detected (should be 'kustomization')"; found=1} /^[^ ]/{flag=0}' "$file" | grep -q "Invalid"; then
                echo "✗ $file: Found invalid postRenderer key 'kustomize'"
                FOUND_ISSUES=$((FOUND_ISSUES + 1))
            fi
        fi
    fi
done

if [ "${FOUND_ISSUES}" -gt 0 ]; then
    echo ""
    echo "Found ${FOUND_ISSUES} invalid postRenderer configuration(s)."
    echo "The correct postRenderer key is 'kustomization', not 'kustomize'."
    exit 1
else
    echo "✓ All HelmRelease postRenderer configurations are valid."
    exit 0
fi
