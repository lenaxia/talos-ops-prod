#!/bin/bash
# Bulk patch spec.upgrade.remediation.retries in HelmRelease files

set -e

# Configuration
RETRY_VALUE="${1:-3}"  # Default to 3 if not specified
TARGET_DIR="${2:-kubernetes/apps}"  # Default to kubernetes/apps

echo "=== Bulk Patching HelmRelease Retry Values ==="
echo "Target directory: $TARGET_DIR"
echo "Retry value: $RETRY_VALUE"
echo ""

# Find all helm-release.yaml files
files=$(find "$TARGET_DIR" -name "helm-release.yaml" -o -name "helmrelease.yaml")

count=0
updated=0
skipped=0

for file in $files; do
    count=$((count + 1))
    
    # Check if file has spec.upgrade section
    if ! yq eval '.spec.upgrade' "$file" > /dev/null 2>&1; then
        echo "⊘ Skipping $file (no spec.upgrade section)"
        skipped=$((skipped + 1))
        continue
    fi
    
    # Check current retry value
    current=$(yq eval '.spec.upgrade.remediation.retries' "$file" 2>/dev/null || echo "null")
    
    if [ "$current" = "$RETRY_VALUE" ]; then
        echo "✓ $file (already $RETRY_VALUE)"
        skipped=$((skipped + 1))
        continue
    fi
    
    # Update the value
    yq eval ".spec.upgrade.remediation.retries = $RETRY_VALUE" -i "$file"
    
    echo "✓ Updated $file ($current → $RETRY_VALUE)"
    updated=$((updated + 1))
done

echo ""
echo "=== Summary ==="
echo "Total files found: $count"
echo "Updated: $updated"
echo "Skipped: $skipped"
echo ""

if [ $updated -gt 0 ]; then
    echo "Review changes with: git diff $TARGET_DIR"
    echo "Commit with: git add $TARGET_DIR && git commit -m 'chore: update helm retry values to $RETRY_VALUE'"
fi