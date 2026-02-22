#!/usr/bin/env bash
set -o errexit
set -o pipefail

# Validate HelmRelease schema compliance
# This script validates that HelmRelease files comply with Flux v2 schema

KUBERNETES_DIR=${1:-./kubernetes}

errors=0
checked=0

echo "=== Validating HelmRelease schema compliance ==="

# Find all HelmRelease files
while IFS= read -r -d $'\0' file; do
    checked=$((checked + 1))
    
    # Check for invalid upgrade.strategy configuration
    # According to Flux v2 spec, if upgrade.strategy exists, it must be an object, not a string
    if yq eval '.spec.upgrade.strategy | type == "str"' "$file" 2>/dev/null; then
        echo "ERROR: Invalid upgrade.strategy found in $file"
        echo "  The 'upgrade.strategy' field, when present, must be an object, not a string."
        echo "  Remove the line or use proper object structure."
        echo ""
        echo "  Current (incorrect):"
        echo "    upgrade:"
        echo "      cleanupOnFail: true"
        echo "      remediation:"
        echo "        retries: 5"
        echo "      strategy: rollback  <-- WRONG (string)"
        echo ""
        echo "  Correct:"
        echo "    upgrade:"
        echo "      cleanupOnFail: true"
        echo "      remediation:"
        echo "        retries: 5"
        echo ""
        errors=$((errors + 1))
    fi
    
    # Check for invalid remediation.strategy configuration
    # According to Flux v2 spec, remediation does not have a strategy field
    if yq eval '.spec.upgrade.remediation.strategy != null' "$file" 2>/dev/null; then
        echo "ERROR: Invalid remediation.strategy found in $file"
        echo "  The 'remediation' section does not support a 'strategy' field in Flux v2."
        echo "  Remove the 'strategy' field from remediation."
        echo ""
        echo "  Current (incorrect):"
        echo "    upgrade:"
        echo "      remediation:"
        echo "        strategy: rollback  <-- WRONG"
        echo "        retries: 3"
        echo ""
        echo "  Correct:"
        echo "    upgrade:"
        echo "      remediation:"
        echo "        retries: 3"
        echo ""
        errors=$((errors + 1))
    fi
done < <(find "$KUBERNETES_DIR/apps" -name "helm-release.yaml" -print0)

echo "=== Validation Summary ==="
echo "Checked: $checked files"
echo "Errors: $errors files"

if [ $errors -gt 0 ]; then
    echo ""
    echo "VALIDATION FAILED: Found $errors file(s) with invalid schema configuration"
    exit 1
else
    echo "VALIDATION PASSED: All HelmRelease files comply with Flux v2 schema"
    exit 0
fi
