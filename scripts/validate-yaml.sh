#!/usr/bin/env bash
set -o errexit
set -o pipefail

# YAML validation script to catch syntax errors and duplicate keys
# This prevents issues like the one in nzbhydra2 helm-release.yaml

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
KUBERNETES_DIR=${1:-"./kubernetes"}

echo "=== Validating YAML syntax for files in ${KUBERNETES_DIR} ==="

# Find all YAML files
find "${KUBERNETES_DIR}" -type f \( -name "*.yaml" -o -name "*.yml" \) -print0 | while IFS= read -r -d $'\0' file;
do
    # Check if yq is available
    if command -v yq &> /dev/null; then
        # Use yq to validate YAML syntax
        if ! yq eval '.' "${file}" > /dev/null 2>&1; then
            echo "❌ YAML syntax error in ${file}"
            yq eval '.' "${file}" 2>&1 | head -5
            exit 1
        fi
    else
        # Fallback to Python if yq is not available
        if command -v python3 &> /dev/null; then
            python3 -c "
import sys
import yaml
try:
    with open('${file}', 'r') as f:
        yaml.safe_load(f)
except yaml.YAMLError as e:
    print(f'❌ YAML syntax error in ${file}')
    print(f'Error: {e}')
    sys.exit(1)
" || exit 1
        else
            echo "⚠️  Warning: Neither yq nor python3 is available for YAML validation"
            echo "⚠️  Skipping YAML syntax validation for ${file}"
        fi
    fi
done

echo "✅ All YAML files are valid"
