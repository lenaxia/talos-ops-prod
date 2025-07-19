#!/bin/bash

# Convert all traefik.containo.us/v1alpha1 Middlewares to traefik.io/v1alpha1
for file in middlewares/*.yaml; do
  if grep -q "traefik.containo.us/v1alpha1" "$file"; then
    echo "Converting $file to v3"
    sed -i 's/traefik.containo.us\/v1alpha1/traefik.io\/v1alpha1/g' "$file"
    
    # Special cases for plugin middlewares
    if grep -q "plugin:" "$file"; then
      echo "  Found plugin middleware - may need manual verification"
    fi
    
    # Add new required fields where needed
    if grep -q "redirectScheme:" "$file" && ! grep -q "permanent:" "$file"; then
      sed -i '/redirectScheme:/a \      permanent: true' "$file"
    fi
  fi
done
