#!/usr/bin/env bash
set -o errexit
set -o pipefail

# Validate YAML syntax for all YAML files in the repository
# This catches indentation errors and other YAML syntax issues early

KUBERNETES_DIR=${1:-"./kubernetes"}

echo "=== Validating YAML syntax in ${KUBERNETES_DIR} ==="

# Count total files and errors
total_files=0
total_errors=0

# Find all YAML files and validate them
find "${KUBERNETES_DIR}" -type f \( -name '*.yaml' -o -name '*.yml' \) -print0 | while IFS= read -r -d $'\0' file; do
    total_files=$((total_files + 1))
    
    # Use Python to validate YAML syntax (more reliable than basic grep/sed checks)
    if ! python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null; then
        echo "✗ YAML syntax error in: $file"
        python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>&1 | grep -E "^Error|yaml:" || echo "  (Use a YAML validator for details)"
        total_errors=$((total_errors + 1))
    fi
done

if [ "$total_errors" -gt 0 ]; then
    echo ""
    echo "Found $total_errors YAML syntax error(s) in $total_files file(s)"
    exit 1
else
    echo "✓ All $total_files YAML files are valid"
fi
