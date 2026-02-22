#!/bin/bash
# Pre-commit hook to validate HelmRelease upgrade.strategy configuration
# Prevents: spec.upgrade.strategy being a string (should be object) or being in wrong location

set -e

echo "Validating HelmRelease upgrade.strategy configurations..."

FAILED=0

# Find all HelmRelease files
HELM_FILES=$(find kubernetes -name "helm-release.yaml" -type f)

for file in $HELM_FILES; do
    # Skip if not a HelmRelease v2
    if ! grep -q "apiVersion: helm.toolkit.fluxcd.io/v2" "$file"; then
        continue
    fi

    # Check if file has upgrade section
    if ! grep -q "^\s\+upgrade:\s*$" "$file"; then
        continue
    fi

    # Extract upgrade section (up to 30 lines after "upgrade:")
    UPGRADE_SECTION=$(awk '/^\s+upgrade:/{flag=1} flag && /^  [^ ]|^    [^ ]/{if(!/^  [a-z]/{exit}} flag{print}}' "$file" | head -30)

    # Check if strategy is directly under upgrade (wrong - should be object or under remediation)
    if echo "$UPGRADE_SECTION" | grep -q "^\s\+strategy:\s\+[a-zA-Z]"; then
        echo "❌ ERROR: $file"
        echo "   Found 'strategy: <string>' directly under 'upgrade:'"
        echo "   Expected: 'strategy:' should be an object with 'type:' field OR under 'upgrade.remediation:'"
        FAILED=1
    fi

    # Check if strategy is properly structured if it exists
    if echo "$UPGRADE_SECTION" | grep -q "^\s\+strategy:\s*$"; then
        # Strategy is an object, check if it has type field
        if ! echo "$UPGRADE_SECTION" | grep -A 5 "^\s\+strategy:\s*$" | grep -q "^\s\+type:"; then
            echo "⚠️  WARNING: $file"
            echo "   'strategy:' object found but missing 'type:' field"
        fi
    fi
done

if [ $FAILED -eq 1 ]; then
    echo ""
    echo "❌ Validation failed! Please fix the HelmRelease upgrade.strategy configuration."
    echo ""
    echo "Correct format 1 (remediation strategy):"
    echo "  upgrade:"
    echo "    remediation:"
    echo "      strategy: rollback"
    echo ""
    echo "Correct format 2 (top-level strategy):"
    echo "  upgrade:"
    echo "    strategy:"
    echo "      type: rollback"
    exit 1
fi

echo "✅ All HelmRelease files validated successfully"
