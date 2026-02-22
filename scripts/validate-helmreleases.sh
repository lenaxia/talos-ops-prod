#!/usr/bin/env bash
set -o errexit
set -o pipefail

# This script validates HelmRelease files for common misconfigurations
# to catch schema validation issues before they reach the CI pipeline.

KUBERNETES_DIR="${1:-./kubernetes}"

echo "=== Checking for common HelmRelease misconfigurations ==="
echo ""
echo "Common HelmRelease pitfalls to avoid:"
echo "1. upgrade.strategy should be an object, not a string"
echo "2. upgrade.remediation.strategy can be a string (e.g., 'rollback')"
echo "3. The 'strategy: rollback' should be nested under 'upgrade.remediation:', not under 'upgrade:' directly"
echo ""
echo "Correct pattern:"
echo "  upgrade:"
echo "    cleanupOnFail: true"
echo "    remediation:"
echo "      retries: 5"
echo "      strategy: rollback  # <-- Correct: nested under remediation"
echo ""
echo "Incorrect pattern (will cause kubeconform to fail):"
echo "  upgrade:"
echo "    cleanupOnFail: true"
echo "    remediation:"
echo "      retries: 5"
echo "    strategy: rollback  # <-- Incorrect: directly under upgrade"
echo ""

# Check for the specific incorrect pattern found in forgejo helm-release.yaml
echo "Checking for upgrade.strategy directly under upgrade..."

ISSUES_FOUND=0

for file in $(find "${KUBERNETES_DIR}" -name "helm-release.yaml" -type f); do
    # Use grep to find files with the pattern: upgrade: followed by strategy: before remediation:
    # This is a simplified check for the specific issue we found
    if grep -A 5 '^\s\+upgrade:' "$file" | grep -q '^\s\+strategy:'; then
        # Additional check: ensure strategy is NOT under remediation
        # Count indentation: strategy should have more spaces than remediation
        upgrade_section=$(awk '/^\s+upgrade:/,/^[^\s]/ {print}' "$file")
        if echo "$upgrade_section" | grep -q '^\s\+strategy:'; then
            # Get indentation levels
            strategy_indent=$(echo "$upgrade_section" | grep '^\s\+strategy:' | head -1 | sed 's/^\(\s*\).*/\1/' | wc -c)
            remediation_indent=$(echo "$upgrade_section" | grep '^\s\+remediation:' | head -1 | sed 's/^\(\s*\).*/\1/' | wc -c 2>/dev/null || echo "0")
            
            # If strategy has same or fewer spaces than remediation, it's likely wrong
            if [ "$strategy_indent" -le "$remediation_indent" ]; then
                echo "ERROR: ${file}: 'strategy:' may be at wrong indentation level"
                echo "       It should be nested under 'remediation:' section"
                ISSUES_FOUND=1
            fi
        fi
    fi
done

echo ""
if [ "$ISSUES_FOUND" -eq 0 ]; then
    echo "Validation complete. No common misconfigurations found."
else
    echo "Validation complete. Found potential misconfigurations!"
    echo "Please review the errors above and fix the HelmRelease files."
    exit 1
fi
