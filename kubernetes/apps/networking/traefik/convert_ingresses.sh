#!/bin/bash

# Update Ingress annotations to use traefik.io prefix
for file in ingresses/*.yaml; do
  if grep -q "traefik.ingress.kubernetes.io" "$file"; then
    echo "Updating annotations in $file"
    sed -i 's/traefik.ingress.kubernetes.io/traefik.io/g' "$file"
    
    # Update middleware references in chains
    sed -i 's/@kubernetescrd/@kubernetes/g' "$file"
  fi
done
