#!/usr/bin/env bash
set -o errexit
set -o pipefail

# Fix old Kustomize patch syntax to new Kustomize v5.x syntax
# Converts: patches: - ./file.yaml
# To:      patches: - path: ./file.yaml

echo "Migrating Kustomize patch syntax to v5.x format..."

find kubernetes -name "kustomization.yaml" -type f | while IFS= read -r file; do
    # Check if file contains old patch syntax (string path without 'path:' key)
    if grep -q "^\s*-\s*\.\/.*\.yaml" "$file" | grep -B1 "^patches:" > /dev/null 2>&1; then
        echo "Migrating: $file"
        
        # Create temporary file
        tmp_file="${file}.tmp"
        
        # Use awk to transform old patch syntax to new format
        awk '
            # Track if we are inside patches section
            /^patches:/ { in_patches = 1; print; next }
            
            # Exit patches section when we hit another top-level field (same or less indentation as patches)
            /^[a-zA-Z]/ && !/^patches:/ && in_patches { in_patches = 0 }
            
            # In patches section, transform string paths to object format
            in_patches && /^\s*-\s*\.\// {
                # Extract the indentation and path
                match($0, /^(\s*)-(\s*)(\.\/.*)$/, arr)
                if (arr[1] != "" && arr[3] != "") {
                    printf "%s- path: %s\n", arr[1], arr[3]
                    next
                }
            }
            
            # Print all other lines unchanged
            { print }
        ' "$file" > "$tmp_file"
        
        # Replace original file
        mv "$tmp_file" "$file"
    fi
done

echo "Migration complete!"
