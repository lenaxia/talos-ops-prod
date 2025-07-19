#!/bin/bash
# Traefik v2 to v3 Migration Script
# Combines all conversion steps into a single script

set -e  # Exit on error

# Backup original files
echo "=== Creating backups ==="
BACKUP_DIR="traefik_migration_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r middlewares/ "$BACKUP_DIR/middlewares"
cp -r ingresses/ "$BACKUP_DIR/ingresses"
echo "Backups created in: $BACKUP_DIR"

# Convert Middlewares
echo -e "\n=== Converting Middlewares ==="
find middlewares/ -type f -name "*.yaml" | while read file; do
    if grep -q "traefik.containo.us/v1alpha1" "$file"; then
        echo "Converting $file to v3"
        # Update API version
        sed -i 's/traefik.containo.us\/v1alpha1/traefik.io\/v1alpha1/g' "$file"
        
        # Add required fields
        if grep -q "redirectScheme:" "$file" && ! grep -q "permanent:" "$file"; then
            sed -i '/redirectScheme:/a \      permanent: true' "$file"
        fi
        
        # Flag plugin middlewares
        if grep -q "plugin:" "$file"; then
            echo "  [NOTE] Plugin middleware detected - please verify manually: $file"
        fi
    fi
done

# Convert Ingresses
echo -e "\n=== Converting Ingresses ==="
find ingresses/ -type f -name "*.yaml" | while read file; do
    # Update annotations
    if grep -q "traefik.ingress.kubernetes.io" "$file"; then
        echo "Updating annotations in $file"
        sed -i 's/traefik.ingress.kubernetes.io/traefik.io/g' "$file"
        sed -i 's/@kubernetescrd/@kubernetes/g' "$file"
    fi
    
    # Update any remaining containo.us references
    if grep -q "traefik.containo.us" "$file"; then
        echo "Fixing remaining containo.us references in $file"
        sed -i 's/apiVersion: traefik.containo.us\/v1alpha1/apiVersion: traefik.io\/v1alpha1/g' "$file"
    fi
done

# Verification
echo -e "\n=== Verification ==="

# Check API versions
echo -e "\n[1/4] Checking API versions:"
grep -r "apiVersion:" middlewares/ ingresses/ | grep -v "kustomize" | sort | uniq -c

# Check annotations
echo -e "\n[2/4] Checking annotations:"
grep -r "traefik.io/router" ingresses/ | sort | uniq

# Check for deprecated references
echo -e "\n[3/4] Checking for deprecated references:"
grep -r "traefik.containo.us" middlewares/ ingresses/ || echo "No deprecated references found"

# Check chain references
echo -e "\n[4/4] Checking chain middleware references:"
find middlewares/ -type f -name "*.yaml" | while read file; do
    if grep -q "chain:" "$file"; then
        echo "Chain in $file:"
        grep -A5 "chain:" "$file" | grep "name:"
    fi
done

# Plugin middleware summary
echo -e "\n=== Plugin Middlewares (Require Manual Verification) ==="
find middlewares/ -type f -name "*.yaml" | while read file; do
    if grep -q "plugin:" "$file"; then
        echo "- $file"
        grep -A2 "plugin:" "$file"
    fi
done | grep -B1 -A2 "plugin:" || echo "No plugin middlewares found"

echo -e "\n=== Migration Summary ==="
echo "1. Backups created in: $BACKUP_DIR"
echo "2. Middlewares and Ingresses converted to Traefik v3"
echo "3. Verification checks completed"
echo ""
echo "Next steps:"
echo "1. Review plugin middlewares (listed above)"
echo "2. Apply changes: kubectl apply -f middlewares/ ingresses/"
echo "3. After confirming everything works, remove old CRDs (script provided below)"
echo ""
echo "To remove old CRDs (run after verification):"
cat <<EOF
kubectl delete crd \\
  ingressroutes.traefik.containo.us \\
  ingressroutetcps.traefik.containo.us \\
  ingressrouteudps.traefik.containo.us \\
  middlewares.traefik.containo.us \\
  middlewaretcps.traefik.containo.us \\
  serverstransports.traefik.containo.us \\
  tlsoptions.traefik.containo.us \\
  tlsstores.traefik.containo.us \\
  traefikservices.traefik.containo.us
EOF
