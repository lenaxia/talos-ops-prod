#!/usr/bin/env bash
# Pre-commit hook and CI validation to catch deprecated Kustomize patches syntax

set -o errexit
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KUBERNETES_DIR="${1:-./kubernetes}"

echo "=== Validating Kustomize patches syntax in ${KUBERNETES_DIR} ==="

# Find all kustomization.yaml files
find "${KUBERNETES_DIR}" -type f -name "kustomization.yaml" -print0 | while IFS= read -r -d $'\0' file; do
  echo "Checking: ${file}"
  
  # Check for deprecated string-based patches (without 'path:' key)
  # This regex matches lines like:
  # patches:
  #   - ./file.yaml  (BAD)
  # But not:
  # patches:
  #   - path: ./file.yaml  (GOOD)
  #   - patch: |-  (GOOD - inline patch)
  #   - target:  (GOOD - patch with target)
  
  # Read the file and check for patches section with string values
  python3 -c "
import sys
import yaml
import os

try:
    with open('${file}', 'r') as f:
        data = yaml.safe_load(f)
    
    if not data or 'patches' not in data:
        sys.exit(0)
    
    patches = data['patches']
    
    # Check if patches is a list
    if not isinstance(patches, list):
        print(f'ERROR: patches must be a list in {file}')
        sys.exit(1)
    
    for i, patch in enumerate(patches):
        # If patch is a string, it's the deprecated format
        if isinstance(patch, str):
            print(f'ERROR: Deprecated patches syntax in {file}:{i}')
            print(f'  Found: - {patch}')
            print(f'  Expected: - path: {patch}')
            sys.exit(1)
    
    sys.exit(0)
    
except yaml.YAMLError as e:
    print(f'WARNING: Could not parse YAML in ${file}: {e}')
    sys.exit(0)
except Exception as e:
    print(f'ERROR: Unexpected error processing ${file}: {e}')
    sys.exit(1)
"
  
  if [ $? -ne 0 ]; then
    echo "FAIL: Invalid patches syntax found in ${file}"
    echo ""
    echo "The 'patches' field must use object syntax, not string paths."
    echo ""
    echo "INCORRECT:"
    echo "  patches:"
    echo "    - ./my-patch.yaml"
    echo ""
    echo "CORRECT:"
    echo "  patches:"
    echo "    - path: ./my-patch.yaml"
    echo ""
    exit 1
  fi
done

echo "=== All Kustomize patches syntax is valid ==="