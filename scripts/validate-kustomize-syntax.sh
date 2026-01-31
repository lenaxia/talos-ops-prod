#!/usr/bin/env bash
# Validate Kustomization files for common syntax errors
# This script checks for:
# - Invalid patches syntax (strings instead of objects)
# - Missing required fields in patch objects
# - Deprecated kustomize syntax

set -o errexit
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

errors_found=0
warnings_found=0

echo "=== Validating Kustomization syntax ==="

find_kustomizations() {
    local dir="$1"
    find "$dir" -type f -name "kustomization.yaml"
}

validate_patches_syntax() {
    local kustomization_file="$1"
    
    if grep -q "^patches:" "$kustomization_file"; then
        # Extract patches section
        local patches_section=$(sed -n '/^patches:/,/^[a-z]/p' "$kustomization_file" | sed '$d')
        
        # Check for string-based patches (invalid syntax)
        if echo "$patches_section" | grep -E "^\s+-\s+[^\s].*\.yaml$" > /dev/null 2>&1; then
            echo -e "${RED}ERROR: Invalid patches syntax in $kustomization_file${NC}"
            echo "  Patches must use object format with 'path' and optional 'target' fields."
            echo "  Invalid format found:"
            grep -A 2 "^patches:" "$kustomization_file" | grep -E "^\s+-\s+[^\s].*\.yaml$" | sed 's/^/    /'
            echo ""
            echo "  Expected format:"
            echo "    patches:"
            echo "      - path: ./patches/example.yaml"
            echo "        target:"
            echo "          kind: Deployment"
            echo "          name: my-app"
            echo ""
            errors_found=$((errors_found + 1))
            return 1
        fi
        
        # Validate that patch objects have 'path' field
        if echo "$patches_section" | grep -E "^\s+-\s+[a-z]+:" > /dev/null 2>&1; then
            if ! echo "$patches_section" | grep "path:" > /dev/null 2>&1; then
                echo -e "${YELLOW}WARNING: Patch objects missing 'path' field in $kustomization_file${NC}"
                echo "  Each patch object should have a 'path' field."
                warnings_found=$((warnings_found + 1))
            fi
        fi
    fi
    
    return 0
}

validate_deprecated_syntax() {
    local kustomization_file="$1"
    
    # Check for deprecated commonLabels
    if grep -q "^commonLabels:" "$kustomization_file"; then
        echo -e "${YELLOW}WARNING: Deprecated 'commonLabels' found in $kustomization_file${NC}"
        echo "  'commonLabels' is deprecated. Use 'labels' instead."
        echo "  Run 'kustomize edit fix' to update automatically."
        echo ""
        warnings_found=$((warnings_found + 1))
    fi
}

main() {
    local kubernetes_dirs=(
        "$REPO_ROOT/kubernetes/flux"
        "$REPO_ROOT/kubernetes/apps"
    )
    
    for dir in "${kubernetes_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            while IFS= read -r -d '' kustomization_file; do
                echo "Checking: $kustomization_file"
                
                validate_patches_syntax "$kustomization_file"
                validate_deprecated_syntax "$kustomization_file"
                
            done < <(find "$dir" -type f -name "kustomization.yaml" -print0)
        fi
    done
    
    echo ""
    echo "=== Validation Summary ==="
    
    if [[ $errors_found -gt 0 ]]; then
        echo -e "${RED}✗ Found $errors_found error(s)${NC}"
        exit 1
    elif [[ $warnings_found -gt 0 ]]; then
        echo -e "${YELLOW}⚠ Found $warnings_found warning(s)${NC}"
        exit 0
    else
        echo -e "${GREEN}✓ All kustomizations are valid${NC}"
        exit 0
    fi
}

main "$@"
