#!/usr/bin/env bash
set -o errexit
set -o pipefail

# Validate HelmRelease upgrade.strategy configuration
# This script checks for incorrect upgrade.strategy configurations in HelmRelease files

KUBERNETES_DIR=${1:-./kubernetes}

errors=0
checked=0

echo "=== Validating HelmRelease upgrade.strategy configurations ==="

# Find all HelmRelease files
while IFS= read -r -d $'\0' file; do
    checked=$((checked + 1))
    
    # Check if the file contains upgrade: section
    if rg -q "^\s+upgrade:" "$file"; then
        # Check for strategy key directly under upgrade (incorrect pattern)
        # The correct pattern is under upgrade.remediation.strategy
        if rg -U "^\s+upgrade:.*\n(\s+cleanupOnFail.*\n|\s+remediation.*\n)*\s+strategy:\s*\w+" "$file" >/dev/null 2>&1; then
            echo "ERROR: Invalid upgrade.strategy found in $file"
            echo "  The 'strategy' field should be under 'upgrade.remediation.strategy', not directly under 'upgrade'"
            echo ""
            echo "  Current (incorrect):"
            echo "    upgrade:"
            echo "      cleanupOnFail: true"
            echo "      remediation:"
            echo "        retries: 5"
            echo "      strategy: rollback  <-- WRONG"
            echo ""
            echo "  Correct:"
            echo "    upgrade:"
            echo "      cleanupOnFail: true"
            echo "      remediation:"
            echo "        retries: 5"
            echo "        strategy: rollback  <-- CORRECT"
            echo ""
            errors=$((errors + 1))
        fi
    fi
done < <(find "$KUBERNETES_DIR/apps" -name "helm-release.yaml" -print0)

echo "=== Validation Summary ==="
echo "Checked: $checked files"
echo "Errors: $errors files"

if [ $errors -gt 0 ]; then
    echo ""
    echo "VALIDATION FAILED: Found $errors file(s) with invalid upgrade.strategy configuration"
    exit 1
else
    echo "VALIDATION PASSED: All HelmRelease files have correct upgrade.strategy configuration"
    exit 0
fi
