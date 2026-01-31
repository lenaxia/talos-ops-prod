#!/usr/bin/env bash

# Validate Kustomization files for common syntax errors
set -eo pipefail

KUBERNETES_DIR="${KUBERNETES_DIR:-./kubernetes}"

echo "Validating Kustomization files..."

errors_found=0

# Find all kustomization.yaml files in the kubernetes directory
while IFS= read -r -d '' file; do
  # Check for invalid patches syntax (string instead of object)
  if grep -qE "^  patches:.*$" "$file" && awk '/^  patches:/,/^[a-z]/ {if (/^  - \.\//) {found=1}} END {exit found?1:0}' "$file"; then
    echo "❌ Invalid patches syntax in $file"
    echo "   Patches must use 'path:' key instead of direct file paths"
    echo "   Example: patches: - ./file.yaml → patches: - path: ./file.yaml"
    errors_found=1
  fi
done < <(find "$KUBERNETES_DIR" -name "kustomization.yaml" -print0)

if [ "$errors_found" -eq 1 ]; then
  echo ""
  echo "Validation failed. Please fix the errors above."
  exit 1
fi

echo "✅ All Kustomization files are valid"
exit 0
