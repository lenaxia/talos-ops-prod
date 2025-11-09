#!/bin/bash
set -e

echo "=== Completing App Template v4.3.0 Upgrade ==="
echo ""

# List of files still needing upgrade
FILES_TO_UPGRADE=(
  "kubernetes/apps/home/node-red/app/helm-release.yaml"
  "kubernetes/apps/home/langserver/app/helm-release.yaml"
  "kubernetes/apps/home/babybuddy-pandaria/app/helm-release.yaml"
  "kubernetes/apps/home/gamevault/app/helm-release.yaml"
  "kubernetes/apps/home/hercules/renewal/helm-release.yaml"
  "kubernetes/apps/home/hercules/classic/helm-release.yaml"
  "kubernetes/apps/home/babybuddy/app/helm-release.yaml"
  "kubernetes/apps/home/babybuddy/base/helm-release.yaml"
  "kubernetes/apps/home/localai/big-agi/helm-release.yaml"
  "kubernetes/apps/home/localai/jupyter/helm-release.yaml"
  "kubernetes/apps/home/localai/vllm/helm-release.yaml"
  "kubernetes/apps/home/localai/open-webui/helm-release.yaml"
  "kubernetes/apps/home/localai/litellm/helm-release.yaml"
  "kubernetes/apps/home/vscode/app/helm-release.yaml"
  "kubernetes/apps/home/zwavejs/app/helm-release.yaml"
  "kubernetes/apps/storage/kopia-web/app/helm-release.yaml"
  "kubernetes/apps/storage/paperless/app/helm-release.yaml"
  "kubernetes/apps/utilities/adguard/app/helm-release.yaml"
  "kubernetes/apps/utilities/it-tools/app/helm-release.yaml"
  "kubernetes/apps/home/home-assistant/app/helm-release.yaml"
  "kubernetes/apps/home/magicmirror/base/helm-release.yaml"
  "kubernetes/apps/home/localai/tabbyapi/helm-release.yaml"
)

echo "Found ${#FILES_TO_UPGRADE[@]} files to upgrade"
echo ""

# Upgrade each file
for file in "${FILES_TO_UPGRADE[@]}"; do
  if [ -f "$file" ]; then
    echo "Upgrading: $file"
    
    # Use sed to replace version lines
    # Match lines like "      version: 3.1.0" or "      version: 3.5.1" or "      version: 2.6.0"
    sed -i 's/^\(      version: \)[0-9]\+\.[0-9]\+\.[0-9]\+$/\14.3.0/' "$file"
    
    # Verify the change
    if grep -q "version: 4.3.0" "$file"; then
      echo "  ✓ Successfully upgraded to 4.3.0"
    else
      echo "  ✗ WARNING: Failed to upgrade $file"
    fi
  else
    echo "  ✗ File not found: $file"
  fi
  echo ""
done

echo "=== Upgrade Complete ==="
echo ""
echo "Verify changes with:"
echo "  git diff kubernetes/apps/"
echo ""
echo "Commit and push:"
echo "  git add kubernetes/apps/"
echo "  git commit -m 'chore: complete app-template v4.3.0 upgrade for remaining apps'"
echo "  git push"
echo ""
echo "Then force Flux to sync:"
echo "  ./scripts/force-flux-sync.sh"