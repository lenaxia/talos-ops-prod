#!/bin/bash

# Simple script to analyze app-template chart versions
set -eo pipefail

# Array of helm release files to check
declare -a FILES=(
    "kubernetes/apps/databases/redis/app/helm-release.yaml"
    "kubernetes/apps/home/fasten/app/helm-release.yaml"
    "kubernetes/apps/home/stablediffusion/app/helm-release.yaml"
    "kubernetes/apps/home/linkwarden/app/helm-release.yaml"
    "kubernetes/apps/home/babybuddy/app/helm-release.yaml"
    "kubernetes/apps/home/monica/app/helm-release.yaml"
    "kubernetes/apps/home/vscode/app/helm-release.yaml"
    "kubernetes/apps/home/langserver/app/helm-release.yaml"
    "kubernetes/apps/home/mosquitto/app/helm-release.yaml"
    "kubernetes/apps/home/browserless/app/helm-release.yaml"
    "kubernetes/apps/home/magicmirror/app/helm-release.yaml"
    "kubernetes/apps/home/redlib/app/helm-release.yaml"
    "kubernetes/apps/home/gamevault/app/helm-release.yaml"
    "kubernetes/apps/home/esphome/app/helm-release.yaml"
    "kubernetes/apps/home/frigate/app/helm-release.yaml"
    "kubernetes/apps/home/home-assistant/app/helm-release.yaml"
    "kubernetes/apps/home/babybuddy-pandaria/app/helm-release.yaml"
    "kubernetes/apps/home/stirling-pdf/app/helm-release.yaml"
    "kubernetes/apps/home/zwavejs/app/helm-release.yaml"
    "kubernetes/apps/home/node-red/app/helm-release.yaml"
    "kubernetes/apps/media/metube/app/helm-release.yaml"
    "kubernetes/apps/media/imaginary/app/helm-release.yaml"
    "kubernetes/apps/media/recyclarr/app/helm-release.yaml"
    "kubernetes/apps/media/nzbhydra2/app/helm-release.yaml"
    "kubernetes/apps/media/tautulli/app/helm-release.yaml"
    "kubernetes/apps/media/bazarr/app/helm-release.yaml"
    "kubernetes/apps/media/plexmetamanager/app/helm-release.yaml"
    "kubernetes/apps/media/jellyfin/app/helm-release.yaml"
    "kubernetes/apps/media/ersatztv/app/helm-release.yaml"
    "kubernetes/apps/media/transmission/app/helm-release.yaml"
    "kubernetes/apps/media/komga/app/helm-release.yaml"
    "kubernetes/apps/media/nzbget/app/helm-release.yaml"
    "kubernetes/apps/media/subgen/app/helm-release.yaml"
    "kubernetes/apps/media/plex/app/helm-release.yaml"
    "kubernetes/apps/media/sonarr/app/helm-release.yaml"
    "kubernetes/apps/media/radarr/app/helm-release.yaml"
    "kubernetes/apps/media/fmd2/app/helm-release.yaml"
    "kubernetes/apps/media/outline/app/helm-release.yaml"
    "kubernetes/apps/networking/webfinger/app/helm-release.yaml"
    "kubernetes/apps/networking/cloudflare-ddns/app/helm-release.yaml"
    "kubernetes/apps/ragnarok/roskills/app/helm-release.yaml"
    "kubernetes/apps/storage/minio/app/helm-release.yaml"
    "kubernetes/apps/storage/kopia-web/app/helm-release.yaml"
    "kubernetes/apps/storage/paperless/app/helm-release.yaml"
    "kubernetes/apps/utilities/uptimekuma/app/helm-release.yaml"
    "kubernetes/apps/utilities/librespeed/app/helm-release.yaml"
    "kubernetes/apps/utilities/vaultwarden/app/helm-release.yaml"
    "kubernetes/apps/utilities/it-tools/app/helm-release.yaml"
    "kubernetes/apps/utilities/adguard/app/helm-release.yaml"
    "kubernetes/apps/utilities/pgadmin/app/helm-release.yaml"
    "kubernetes/apps/utilities/openldap/app/helm-release.yaml"
    "kubernetes/apps/utilities/vaultwarden-ldap/app/helm-release.yaml"
    "kubernetes/apps/utilities/changedetection/app/helm-release.yaml"
    "kubernetes/apps/utilities/brother-ql-web/app/helm-release.yaml"
    "kubernetes/apps/utilities/guacamole/app/helm-release.yaml"
)

OUTPUT_FILE="app-template-versions-report.md"

# Start the markdown report
cat > "$OUTPUT_FILE" << 'EOF'
# App-Template Chart Version Analysis Report

This report shows all helm releases using the bjw-s app-template chart and their current versions.

## Summary

EOF

# Temporary file to store results
TEMP_FILE=$(mktemp)

# Process each file
for file in "${FILES[@]}"; do
    if [[ -f "$file" ]]; then
        chart_name=$(yq -r '.spec.chart.spec.chart' "$file" 2>/dev/null || echo "N/A")
        version=$(yq -r '.spec.chart.spec.version' "$file" 2>/dev/null || echo "N/A")
        
        if [[ "$chart_name" == "app-template" ]]; then
            app_name=$(echo "$file" | awk -F'/' '{print $(NF-2)}')
            echo "$version|$app_name|$file" >> "$TEMP_FILE"
        fi
    fi
done

# Count versions
declare -A version_counts=()
while IFS='|' read -r version app file; do
    if [[ -n "$version" && "$version" != "N/A" ]]; then
        if [[ -z "${version_counts[$version]:-}" ]]; then
            version_counts[$version]=1
        else
            ((version_counts[$version]++))
        fi
    fi
done < "$TEMP_FILE"

# Write version distribution
echo "### Version Distribution" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
for version in $(printf '%s\n' "${!version_counts[@]}" | sort -V); do
    count=${version_counts[$version]}
    echo "- **Version $version**: $count release(s)" >> "$OUTPUT_FILE"
done

echo "" >> "$OUTPUT_FILE"
echo "## Detailed Breakdown" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Write detailed breakdown
current_version=""
while IFS='|' read -r version app file; do
    if [[ "$version" != "$current_version" ]]; then
        if [[ -n "$current_version" ]]; then
            echo "" >> "$OUTPUT_FILE"
        fi
        current_version="$version"
        echo "### Version $version" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
    fi
    echo "- **$app**" >> "$OUTPUT_FILE"
    echo "  - Path: \`$file\`" >> "$OUTPUT_FILE"
done < <(sort -V -t'|' -k1 "$TEMP_FILE")

# Cleanup
rm "$TEMP_FILE"

echo ""
echo "Report generated: $OUTPUT_FILE"