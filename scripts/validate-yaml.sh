#!/usr/bin/env bash
# Validates YAML files for syntax errors

set -o errexit
set -o pipefail

EXIT_CODE=0
FILES_CHECKED=0
ERRORS_FOUND=0

echo "=== Validating YAML files in kubernetes/ ==="

# Find all YAML files in kubernetes/ directory
while IFS= read -r -d '' file; do
    # Skip .sops.yaml files as they contain encryption metadata
    if [[ "$file" == *.sops.yaml ]]; then
        continue
    fi

    FILES_CHECKED=$((FILES_CHECKED + 1))

    # Check for tabs (YAML should only use spaces)
    if grep -q $'\t' "$file"; then
        echo "❌ ERROR in $file: Found tabs (YAML must use spaces only)"
        ERRORS_FOUND=$((ERRORS_FOUND + 1))
        EXIT_CODE=1
        continue
    fi

    # Validate YAML syntax using Python
    if ! python3 -c "
import sys
import yaml

try:
    with open('$file', 'r') as f:
        yaml.safe_load(f)
except yaml.YAMLError as e:
    print(f'YAML Error: {e}')
    sys.exit(1)
" 2>/dev/null; then
        echo "❌ ERROR in $file: Invalid YAML syntax"
        ERRORS_FOUND=$((ERRORS_FOUND + 1))
        EXIT_CODE=1
    fi
done < <(find kubernetes/ -name "*.yaml" -type f -print0)

echo ""
echo "Files checked: $FILES_CHECKED"
echo "Errors found: $ERRORS_FOUND"

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ YAML validation failed"
    echo "Please fix the errors above before committing or merging"
    exit 1
else
    echo "✅ All YAML files are valid"
    exit 0
fi
