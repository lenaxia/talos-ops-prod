#!/usr/bin/env bash
# Validates YAML files for syntax errors
# This script checks all YAML files in the repository for valid YAML syntax

set -o errexit
set -o pipefail

EXIT_CODE=0
VALIDATOR_CMD=""

# Check if python3 is available
if command -v python3 &> /dev/null; then
    VALIDATOR_CMD="python3 -c 'import sys, yaml; yaml.safe_load_all(sys.stdin)'"
elif command -v python &> /dev/null; then
    VALIDATOR_CMD="python -c 'import sys, yaml; yaml.safe_load_all(sys.stdin)'"
else
    echo "❌ ERROR: Neither python3 nor python is available for YAML validation"
    exit 1
fi

echo "=== Validating YAML files for syntax errors ==="

# Find all YAML files
find . -name "*.yaml" -o -name "*.yml" | while IFS= read -r file; do
    # Skip hidden files and common exclusions
    if [[ "$file" =~ ^\./(\.|node_modules|\.git) ]]; then
        continue
    fi

    # Validate the file
    if ! cat "$file" | eval "$VALIDATOR_CMD" &> /dev/null; then
        echo "❌ ERROR: Invalid YAML syntax in $file"
        cat "$file" | eval "$VALIDATOR_CMD" 2>&1 | sed 's/^/   /'
        EXIT_CODE=1
    fi
done

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ YAML validation failed"
    exit 1
else
    echo "✅ All YAML files are valid"
    exit 0
fi
