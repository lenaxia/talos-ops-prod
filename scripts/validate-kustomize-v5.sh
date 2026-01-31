#!/usr/bin/env bash
# Kustomize v5.x compatibility validation script
# This script validates Kustomization files for Kustomize v5.x syntax compatibility

set -o errexit
set -o pipefail

KUBERNETES_DIR="${KUBERNETES_DIR:-./kubernetes}"
ERRORS_FOUND=0

echo "=== Checking Kustomize v5.x compatibility ==="
echo ""

find "${KUBERNETES_DIR}" -type f -name "kustomization.yaml" -print0 | while IFS= read -r -d $'\0' file; do
    # Check for patches with string values instead of path objects
    if grep -qE "^\s+-\s+[^\s]+\.yaml\s*$" "${file}" 2>/dev/null; then
        # Check if it's under patches: section
        if awk '/^patches:/,/^([^ ]|$)/' "${file}" | grep -qE "^\s+-\s+[^\s]+\.yaml\s*$"; then
            echo "ERROR: ${file} uses deprecated patches syntax (string instead of path: object)"
            awk '/^patches:/,/^([^ ]|$)/' "${file}" | grep -nE "^\s+-\s+[^\s]+\.yaml\s*$" | sed 's/^/  Line /'
            ERRORS_FOUND=1
        fi
    fi

    # Check for commonLabels deprecation
    if grep -q "^\s*commonLabels:" "${file}"; then
        echo "WARNING: ${file} uses deprecated commonLabels (use labels: instead)"
        grep -n "^\s*commonLabels:" "${file}" | sed 's/^/  Line /'
    fi
done

if [ "${ERRORS_FOUND}" -eq 0 ]; then
    echo "✓ No Kustomize v5.x compatibility issues found"
    exit 0
else
    echo ""
    echo "✗ Kustomize v5.x compatibility issues found"
    echo "Please update patches syntax from:"
    echo "  patches:"
    echo "    - ./patch.yaml"
    echo ""
    echo "to:"
    echo "  patches:"
    echo "    - path: ./patch.yaml"
    exit 1
fi
