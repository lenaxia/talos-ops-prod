#!/usr/bin/env bash
set -o errexit
set -o pipefail

# Validate Kustomization files have correct patches format
# This script checks that patches in kustomization.yaml files follow the correct format:
# patches:
#   - path: <path-to-patch-file>
#     target:
#       kind: <resource-kind>
#       name: <resource-name>
#       version: <api-version> # optional
#       group: <api-group> # optional

echo "=== Validating Kustomization patches format ==="

exit_code=0

# Find all kustomization.yaml files
while IFS= read -r -d '' file; do
    echo "Checking $file"
    
    # Extract patches section from the kustomization file
    if yq eval '.patches // []' "$file" > /dev/null 2>&1; then
        # Check if patches is a list
        patches=$(yq eval '.patches // []' "$file")
        
        # If patches is not empty, validate format
        if [ "$patches" != "null" ] && [ "$patches" != "[]" ]; then
            # Check each patch entry
            patch_count=$(yq eval '.patches | length' "$file")
            
            for ((i=0; i<patch_count; i++)); do
                # Check if the patch has both 'path' and 'target' keys
                has_path=$(yq eval ".patches[$i].path" "$file")
                has_target=$(yq eval ".patches[$i].target" "$file")
                
                if [ "$has_path" == "null" ] && [ "$has_target" == "null" ]; then
                    # This is the old format (just a string)
                    echo "❌ ERROR: $file contains patch at index $i with old format (string only)"
                    echo "   Expected format with 'path' and 'target' keys"
                    yq eval ".patches[$i]" "$file" | sed 's/^/   /'
                    exit_code=1
                elif [ "$has_path" == "null" ]; then
                    echo "⚠️  WARNING: $file patch at index $i is missing 'path' key"
                    exit_code=1
                elif [ "$has_target" == "null" ]; then
                    echo "⚠️  WARNING: $file patch at index $i is missing 'target' key"
                    exit_code=1
                fi
            done
        fi
    fi
done < <(find kubernetes -type f -name "kustomization.yaml" -print0)

if [ $exit_code -ne 0 ]; then
    echo ""
    echo "❌ Kustomization patches validation failed!"
    echo "Please update patches to use the correct format:"
    echo ""
    echo "patches:"
    echo "  - path: ./patches/my-patch.yaml"
    echo "    target:"
    echo "      kind: HelmRelease"
    echo "      name: my-release"
    exit 1
fi

echo "✅ All Kustomization patches are properly formatted"
exit 0
