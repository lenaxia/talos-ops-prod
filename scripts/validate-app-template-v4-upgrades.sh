#!/bin/bash
set -e

echo "=== App-Template v4.3.0 Upgrade Validation ==="
echo ""

# Find all helm-release.yaml files that use app-template
files=$(find kubernetes/apps -name "helm-release.yaml" -type f)

total=0
v4_count=0
v3_count=0
v2_count=0
other_count=0
errors=0

for file in $files; do
    # Check if it's an app-template chart
    chart=$(yq -r '.spec.chart.spec.chart' "$file" 2>/dev/null || echo "")
    
    if [[ "$chart" == "app-template" ]]; then
        total=$((total + 1))
        version=$(yq -r '.spec.chart.spec.version' "$file")
        
        # Validate YAML syntax
        if ! yq -r '.' "$file" > /dev/null 2>&1; then
            echo "❌ YAML Error: $file"
            errors=$((errors + 1))
            continue
        fi
        
        # Count by version
        if [[ "$version" =~ ^4\. ]]; then
            v4_count=$((v4_count + 1))
            echo "✓ v$version: $file"
        elif [[ "$version" =~ ^3\. ]]; then
            v3_count=$((v3_count + 1))
            echo "⚠ v$version (not upgraded): $file"
        elif [[ "$version" =~ ^2\. ]]; then
            v2_count=$((v2_count + 1))
            echo "⚠ v$version (not upgraded): $file"
        else
            other_count=$((other_count + 1))
            echo "? v$version: $file"
        fi
    fi
done

echo ""
echo "=== Summary ==="
echo "Total app-template releases: $total"
echo "✓ Upgraded to v4.x: $v4_count"
echo "⚠ Still on v3.x: $v3_count"
echo "⚠ Still on v2.x: $v2_count"
echo "? Other versions: $other_count"
echo "❌ YAML errors: $errors"
echo ""

if [[ $v4_count -eq $total ]] && [[ $errors -eq 0 ]]; then
    echo "✅ All app-template releases successfully upgraded to v4.x!"
    exit 0
else
    echo "⚠️ Some releases not upgraded or have errors"
    exit 1
fi