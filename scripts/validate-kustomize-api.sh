#!/usr/bin/env bash
# Systematic kustomize validation to prevent API incompatibility issues
set -o errexit
set -o pipefail

echo "=== Validating kustomize API compatibility ==="

# Check if kustomize is installed
if ! command -v kustomize &> /dev/null; then
    echo "ERROR: kustomize not found in PATH"
    exit 1
fi

# Get kustomize version
KUSTOMIZE_VERSION=$(kustomize version --short 2>&1 | grep -oP 'v\d+\.\d+\.\d+')
echo "Using kustomize version: ${KUSTOMIZE_VERSION}"

# Extract major version
KUSTOMIZE_MAJOR=$(echo "${KUSTOMIZE_VERSION}" | cut -d'.' -f1 | sed 's/v//')
echo "Major version: ${KUSTOMIZE_MAJOR}"

# For kustomize v5.x, validate patches syntax
if [ "${KUSTOMIZE_MAJOR}" -ge 5 ]; then
    echo "Validating patches syntax for kustomize v5+..."
    
    # Find all kustomization.yaml files
    find kubernetes -type f -name "kustomization.yaml" -print0 | while IFS= read -r -d $'\0' file; do
        echo "Checking: ${file}"
        
        # Check if file uses old patches syntax
        if grep -q '^patches:$' "${file}" && grep -qA 10 '^patches:$' "${file}" | grep -q -E '^\s+-\s+[^[:space:]]+\.yaml$'; then
            echo "  WARNING: Old patches syntax detected in ${file}"
            echo "  Patches in kustomize v5+ should use 'path:' or 'patch:' keys"
            
            # Show the problematic patches section
            grep -A 5 '^patches:$' "${file}" | sed 's/^/    /'
        fi
    done
fi

echo "=== Validation complete ==="
