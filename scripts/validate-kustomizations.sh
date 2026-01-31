#!/usr/bin/env bash
# Validates Kustomization files for common syntax errors

set -o errexit
set -o pipefail

EXIT_CODE=0

# Check all kustomization.yaml files
echo "=== Checking Kustomization files for deprecated syntax ==="
find . -name "kustomization.yaml" -type f | while IFS= read -r file; do
    # Check for bare string patches (deprecated in Kustomize v5.0+)
    if grep -qE '^(\s+)-\s+[a-zA-Z./].*' "$file" | grep -vE '^(\s+)-\s+(path:|patch:|target:|#)'; then
        # Check if it's in patches section
        if grep -A 100 '^patches:' "$file" | grep -qE '^\s+-\s+[a-zA-Z./]'; then
            echo "❌ ERROR in $file: Found bare string in patches (deprecated in Kustomize v5.0+)"
            echo "   Use: - path: ./patch.yaml  instead of  - ./patch.yaml"
            EXIT_CODE=1
        fi
    fi

    # Check for deprecated commonLabels
    if grep -q '^\s*commonLabels:' "$file"; then
        echo "⚠️  WARNING in $file: 'commonLabels' is deprecated, use 'labels' instead"
        echo "   Run: kustomize edit fix to update automatically"
    fi
done

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Kustomization validation failed"
    exit 1
else
    echo "✅ Kustomization validation passed"
    exit 0
fi