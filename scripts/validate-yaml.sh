#!/usr/bin/env bash
# Validates YAML files for duplicate keys and syntax errors

set -o errexit
set -o pipefail

EXIT_CODE=0

# Check all YAML files in kubernetes directory
echo "=== Checking YAML files for syntax errors and duplicate keys ==="
find ./kubernetes -name "*.yaml" -o -name "*.yml" | sort | while IFS= read -r file; do
    # Use python to detect duplicate keys (more reliable than basic parsers)
    if command -v python3 &> /dev/null; then
        python3 -c "
import sys
import yaml

try:
    with open('$file', 'r') as f:
        yaml.safe_load(f)
except yaml.composer.ComposerError as e:
    print(f'❌ ERROR in $file: Duplicate key found')
    print(f'   {e}')
    sys.exit(1)
except yaml.scanner.ScannerError as e:
    print(f'❌ ERROR in $file: YAML syntax error')
    print(f'   {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ ERROR in $file: {e}')
    sys.exit(1)
" || EXIT_CODE=1
    else
        # Fallback: Use yamllint if available
        if command -v yamllint &> /dev/null; then
            yamllint -d "{rules: {key-duplicates: enable, indentation: enable}}" "$file" || EXIT_CODE=1
        else
            echo "⚠️  WARNING: python3 or yamllint not found, skipping deep YAML validation for $file"
        fi
    fi
done

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ YAML validation failed"
    exit 1
else
    echo "✅ YAML validation passed"
    exit 0
fi
