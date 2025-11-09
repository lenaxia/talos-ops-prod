#!/bin/bash
set -e

echo "=== App-Template v4 Immutable Field Fix ==="
echo ""
echo "This script deletes and recreates deployments/statefulsets that have immutable"
echo "field conflicts when upgrading from v3 to v4."
echo ""
echo "The issue: v4 changes the selector labels, which are immutable in Kubernetes."
echo "Solution: Delete the deployment/statefulset and let Flux recreate it with new labels."
echo ""
echo "⚠️  IMPORTANT: PVCs will NOT be deleted and data will be preserved!"
echo "   - Deployments reference existing PVCs by name"
echo "   - StatefulSets do NOT delete PVCs when deleted"
echo "   - All data remains intact during recreation"
echo ""

# List of applications that need deployment recreation
APPS=(
    "home/browserless"
    "home/redlib"
    "media/imaginary"
    "media/bazarr"
    "media/tautulli"
    "media/plexmetamanager"
    "media/ersatztv"
    "media/komga"
    "media/fmd2"
    "media/metube"
    "networking/webfinger"
    "networking/cloudflare-ddns"
    "utilities/uptimekuma"
    "utilities/librespeed"
    "utilities/changedetection"
    "utilities/brother-ql-web"
    "utilities/openldap"
    "utilities/vaultwarden-ldap"
    "home/esphome"
    "home/frigate"
    "home/mosquitto"
    "home/stirling-pdf"
    "media/jellyfin"
    "media/plex"
    "storage/minio"
    "utilities/pgadmin"
    "utilities/guacamole"
    "databases/redis"
    "home/monica"
    "home/fasten"
    "home/linkwarden"
    "home/stablediffusion"
    "ragnarok/roskills"
    "home/magicmirror"
)

echo "Applications to process: ${#APPS[@]}"
echo ""

read -p "Do you want to proceed? This will cause brief downtime for each app. (yes/no): " confirm
if [[ "$confirm" != "yes" ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Starting deployment recreation..."
echo ""

for app in "${APPS[@]}"; do
    namespace=$(echo "$app" | cut -d'/' -f1)
    name=$(echo "$app" | cut -d'/' -f2)
    
    echo "Processing $namespace/$name..."
    
    # Check if deployment exists
    if kubectl get deployment -n "$namespace" "$name" &>/dev/null; then
        echo "  - Found deployment, deleting..."
        kubectl delete deployment -n "$namespace" "$name" --wait=false
        echo "  - Deployment deleted. Flux will recreate it."
    # Check if statefulset exists
    elif kubectl get statefulset -n "$namespace" "$name" &>/dev/null; then
        echo "  - Found statefulset, deleting..."
        kubectl delete statefulset -n "$namespace" "$name" --wait=false
        echo "  - StatefulSet deleted. Flux will recreate it."
        echo "  - Note: PVCs are preserved and will be reattached."
    else
        echo "  - Neither deployment nor statefulset found, skipping."
    fi
    
    # Small delay to avoid overwhelming the API server
    sleep 1
done

echo ""
echo "=== Deployment Recreation Complete ==="
echo ""
echo "Flux will now recreate the deployments with the correct v4 labels."
echo "Monitor the reconciliation:"
echo "  flux get helmreleases -A --watch"
echo ""
echo "Check pod status:"
echo "  kubectl get pods -A | grep -v 'Running\|Completed'"
echo ""