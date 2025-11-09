#!/bin/bash
set -e

echo "=== Forcing Flux to Sync Latest Git Changes ==="
echo ""

echo "1. Current Flux GitRepository status:"
CURRENT_REVISION=$(kubectl get gitrepository flux-system -n flux-system -o jsonpath='{.status.artifact.revision}' 2>/dev/null || echo "Cannot access cluster")
echo "   Flux is on: $CURRENT_REVISION"
echo ""

echo "2. Current Git HEAD:"
GIT_HEAD=$(git rev-parse HEAD)
echo "   Git HEAD: $GIT_HEAD"
echo ""

if [ "$CURRENT_REVISION" = "$GIT_HEAD" ]; then
  echo "   ✓ Flux is already on the latest commit"
else
  echo "   ⚠ Flux is behind - needs sync"
fi
echo ""

echo "3. Forcing GitRepository reconciliation..."
kubectl annotate gitrepository flux-system -n flux-system \
  reconcile.fluxcd.io/requestedAt="$(date +%s)" --overwrite

echo "   Waiting 15 seconds for Git sync..."
sleep 15

echo ""
echo "4. New GitRepository status:"
NEW_REVISION=$(kubectl get gitrepository flux-system -n flux-system -o jsonpath='{.status.artifact.revision}' 2>/dev/null || echo "Cannot get status")
echo "   Flux is now on: $NEW_REVISION"
echo ""

echo "5. Forcing all Kustomizations to reconcile..."
kubectl get kustomization -A -o name | xargs -I {} kubectl annotate {} \
  reconcile.fluxcd.io/requestedAt="$(date +%s)" --overwrite

echo ""
echo "6. Waiting 30 seconds for reconciliation..."
sleep 30

echo ""
echo "7. Checking HelmRelease status for upgraded apps..."
echo ""
kubectl get helmrelease -A | grep -E "(NAMESPACE|babybuddy|home-assistant|vscode|kopia-web|node-red)" | head -15 || true

echo ""
echo "=== Reconciliation Complete ==="
echo ""
echo "Monitor ongoing reconciliation with:"
echo "  watch -n 5 'flux get hr -A | grep -v Succeeded'"
echo ""
echo "Check for any failures:"
echo "  flux get hr -A | grep -v Succeeded"
echo ""
echo "View specific HelmRelease details:"
echo "  flux get hr <name> -n <namespace>"
echo "  kubectl describe hr <name> -n <namespace>"