#!/usr/bin/env bash
# Validates YAML files for duplicate keys and other common YAML syntax errors

set -o errexit
set -o pipefail

EXIT_CODE=0
VALIDATION_ERRORS=0

echo "=== Validating YAML files for duplicate keys ==="

# Check if yamllint is available
if ! command -v yamllint &> /dev/null; then
    echo "⚠️  yamllint not found. Installing..."
    # Try pip install
    if command -v pip3 &> /dev/null; then
        pip3 install yamllint 2>/dev/null || pip install yamllint 2>/dev/null
    elif command -v python3 &> /dev/null; then
        python3 -m pip install yamllint 2>/dev/null
    else
        echo "❌ ERROR: Cannot install yamllint. Please install it manually."
        echo "   pip install yamllint"
        exit 1
    fi
fi

# Find and validate all YAML files in the kubernetes directory
# Exclude .sops.yaml files as they are encrypted
while IFS= read -r -d $'\0' file; do
    # Skip sops encrypted files
    if [[ "$file" == *.sops.yaml ]]; then
        continue
    fi

    # Validate with yamllint
    if ! yamllint -d "{extends: default, rules: {key-ordering: disable, line-length: disable, comments: disable, indentation: disable}}" "$file" 2>/dev/null; then
        EXIT_CODE=1
        VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
    fi
done < <(find ./kubernetes -name "*.yaml" -type f -print0)

# Check for duplicate keys using python/yq
echo ""
echo "=== Checking for duplicate keys in YAML files ==="

# Use python to validate YAML structure
python3 -c "
import sys
import yaml

def check_duplicates(filename):
    try:
        with open(filename, 'r') as f:
            # Use safe_load to prevent code execution
            try:
                data = yaml.safe_load(f)
                # If we get here, parsing succeeded
                return None
            except yaml.composer.ComposerError as e:
                if 'mapping keys' in str(e) and 'already defined' in str(e):
                    return str(e)
                raise
    except Exception as e:
        # Ignore errors from encrypted files or other non-standard YAML
        return None

# Read files from stdin
import sys
for line in sys.stdin:
    line = line.strip()
    if line.endswith('.sops.yaml'):
        continue
    error = check_duplicates(line)
    if error:
        print(f'❌ ERROR in {line}: {error}')
        sys.exit(1)
" < <(find ./kubernetes -name "*.yaml" -type f ! -name "*.sops.yaml" -print0 | tr '\0' '\n')

if [ $? -ne 0 ]; then
    EXIT_CODE=1
    VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
fi

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ YAML validation failed with $VALIDATION_ERRORS error(s)"
    echo ""
    echo "Common issues to fix:"
    echo "   1. Duplicate mapping keys - check indentation"
    echo "   2. Incorrect YAML syntax - use spaces, not tabs"
    echo "   3. Invalid YAML structure - validate with yamllint"
    exit 1
else
    echo "✅ YAML validation passed"
    exit 0
fi
