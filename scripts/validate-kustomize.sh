#!/usr/bin/env bash
# Script to validate Kustomization files for deprecated patches syntax

set -o errexit
set -o pipefail

KUBERNETES_DIR="${1:-./kubernetes}"
ERRORS=0

echo "=== Checking for deprecated patches syntax in Kustomization files ==="

# Find all kustomization.yaml files
find "${KUBERNETES_DIR}" -type f \( -name "kustomization.yaml" -o -name "kustomization.yml" \) -print0 | while IFS= read -r -d $'\0' file; do
    # Check for patches with deprecated string syntax (line starts with - followed by a path string without 'path:' prefix)
    # We look for lines like:
    #   - ./patches/file.yaml  (BAD)
    # instead of:
    #   - path: ./patches/file.yaml  (GOOD)
    
    if yq eval '.patches.[] | select(.path == null and .patch == null) | select(type == "!!str")' "$file" 2>/dev/null | grep -q .; then
        echo "❌ ERROR: ${file} contains deprecated patches syntax"
        echo "   Found patches using string syntax instead of object syntax."
        echo "   Please update to use 'path:' key for each patch."
        yq eval '.patches.[] | select(.path == null and .patch == null) | select(type == "!!str")' "$file" 2>/dev/null | sed 's/^/     /'
        ERRORS=$((ERRORS + 1))
    fi
done

# Also check for patchesStr (deprecated field)
find "${KUBERNETES_DIR}" -type f \( -name "kustomization.yaml" -o -name "kustomization.yml" \) -print0 | while IFS= read -r -d $'\0' file; do
    if yq eval '.patchesStr' "$file" 2>/dev/null | grep -q -v null; then
        echo "❌ ERROR: ${file} contains deprecated 'patchesStr' field"
        echo "   Please rename 'patchesStr' to 'patches' and update to object syntax."
        ERRORS=$((ERRORS + 1))
    fi
done

if [ ${ERRORS} -gt 0 ]; then
    echo ""
    echo "Found ${ERRORS} error(s) in Kustomization files."
    echo ""
    echo "Fix example:"
    echo "  OLD: patches:"
    echo "       - ./patches/file.yaml"
    echo ""
    echo "  NEW: patches:"
    echo "       - path: ./patches/file.yaml"
    exit 1
fi

echo "✅ All Kustomization files use correct patches syntax"
exit 0
