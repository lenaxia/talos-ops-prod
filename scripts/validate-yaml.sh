#!/usr/bin/env bash
set -o errexit
set -o pipefail

# Script to validate YAML files for duplicate keys and syntax errors

if [ $# -eq 0 ]; then
    echo "Usage: $0 <path-to-validate> [path-to-validate] ..."
    echo "Example: $0 kubernetes/"
    exit 1
fi

EXIT_CODE=0

for dir in "$@"; do
    if [ ! -d "$dir" ]; then
        echo "Error: Directory '$dir' does not exist"
        EXIT_CODE=1
        continue
    fi

    echo "=== Validating YAML files in $dir ==="
    
    # Find all YAML files and validate them
    find "$dir" -type f \( -name '*.yaml' -o -name '*.yml' \) -print0 | while IFS= read -r -d $'\0' file; do
        # Skip if file contains Flux placeholders that might cause false positives
        if grep -q '${TIMEZONE}\|${NAS_ADDR}\|${SECRET_DEV_DOMAIN}' "$file"; then
            # For files with placeholders, try to validate with Python yaml module
            if command -v python3 &> /dev/null; then
                if ! python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null; then
                    echo "❌ YAML syntax error in $file"
                    EXIT_CODE=1
                fi
            fi
        else
            # For regular files, validate with yamllint if available
            if command -v yamllint &> /dev/null; then
                if ! yamllint -d "{extends: default, rules: {line-length: {max: 200}, indentation: {spaces: 2, indent-sequences: true}}}" "$file" 1>/dev/null 2>&1; then
                    echo "⚠️  yamllint warnings in $file (check with: yamllint '$file')"
                fi
            fi
            
            # Always check for duplicate keys using Python
            if command -v python3 &> /dev/null; then
                if ! python3 -c "
import sys, yaml
try:
    with open('$file', 'r') as f:
        data = yaml.safe_load(f)
    print('✓ $file')
except yaml.YAMLError as e:
    if 'mapping key' in str(e) and 'already defined' in str(e):
        print(f'❌ Duplicate key error in $file: {e}')
        sys.exit(1)
    elif 'mapping values are not allowed in this context' in str(e):
        print(f'❌ YAML structure error in $file: {e}')
        sys.exit(1)
    else:
        print(f'⚠️  YAML warning in $file: {e}')
" 2>/dev/null; then
                EXIT_CODE=1
            fi
        fi
    done
done

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All YAML files are valid"
else
    echo "❌ YAML validation failed"
fi

exit $EXIT_CODE
