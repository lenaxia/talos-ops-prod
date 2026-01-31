#!/usr/bin/env bash
set -o errexit
set -o pipefail

# Validate Kustomization patches syntax to prevent unmarshal errors
# This script checks for incorrect patches: syntax in kustomization.yaml files

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KUBERNETES_DIR="${SCRIPT_DIR}/../kubernetes"

ERRORS_FOUND=0

echo "=== Checking Kustomization patches syntax ==="

find "${KUBERNETES_DIR}" -type f -name "kustomization.yaml" -print0 | while IFS= read -r -d $'\0' file; do
    # Check for patches: with string values (incorrect syntax)
    if grep -A 2 "^patches:" "$file" | grep -q "^\s*-\s*[^{]"; then
        # Check if the line after patches: contains a string path instead of path: keyword
        if awk '/^patches:/ {found=1; next} found && /^\s*-\s*[^{]/ && !/^\s*-\s*path:/ {print FILENAME":"NR; exit}' "$file" > /dev/null 2>&1; then
            echo "❌ ERROR: Invalid patches syntax in $file"
            echo "   The 'patches:' field requires object format with 'path:' and optional 'target:' fields."
            echo "   Incorrect: patches: [./file.yaml]"
            echo "   Correct:   patches: [- path: ./file.yaml, target: {...}]"
            ERRORS_FOUND=1
        fi
    fi
done

if [ "${ERRORS_FOUND}" -eq 0 ]; then
    echo "✅ All Kustomization files have valid patches syntax"
    exit 0
else
    echo "❌ Found Kustomization files with invalid patches syntax"
    exit 1
fi
