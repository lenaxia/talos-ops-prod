#!/bin/bash

# Script to analyze app-template chart versions across helm releases
# This script extracts version information from helm-release.yaml files

set -eo pipefail

# Detect which yq version is installed
YQ_VERSION=$(yq --version 2>&1 || echo "unknown")
if [[ "$YQ_VERSION" == *"mikefarah"* ]] || [[ "$YQ_VERSION" == *"version 4"* ]]; then
    YQ_TYPE="go"
elif [[ "$YQ_VERSION" == *"jq wrapper"* ]] || [[ "$YQ_VERSION" == *"version 2"* ]] || [[ "$YQ_VERSION" == *"version 3"* ]]; then
    YQ_TYPE="python"
else
    YQ_TYPE="python"  # Default to python syntax
fi

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if yq is installed
if ! command -v yq &> /dev/null; then
    echo -e "${RED}Error: yq is not installed. Please install yq to run this script.${NC}"
    echo "Install with: brew install yq (macOS) or snap install yq (Linux)"
    exit 1
fi

echo "Detected yq type: $YQ_TYPE"
echo ""

# Temporary file to store results
TEMP_FILE=$(mktemp)

echo -e "${BLUE}==================================================================${NC}"
echo -e "${BLUE}  App-Template Chart Version Analysis${NC}"
echo -e "${BLUE}==================================================================${NC}"
echo ""

# Process each file
for file in "${FILES[@]}"; do
    if [[ -f "$file" ]]; then
        # Extract chart name and version based on yq type
        if [[ "$YQ_TYPE" == "go" ]]; then
            chart_name=$(yq eval '.spec.chart.spec.chart' "$file" 2>/dev/null || echo "N/A")
            version=$(yq eval '.spec.chart.spec.version' "$file" 2>/dev/null || echo "N/A")
        else
            # Python yq syntax
            chart_name=$(yq -r '.spec.chart.spec.chart' "$file" 2>/dev/null || echo "N/A")
            version=$(yq -r '.spec.chart.spec.version' "$file" 2>/dev/null || echo "N/A")
        fi
        
        # Only process if it's an app-template chart
        if [[ "$chart_name" == "app-template" ]]; then
            echo "$version|$file" >> "$TEMP_FILE"
        fi
    else
        echo -e "${YELLOW}Warning: File not found: $file${NC}"
    fi
done

# Check if we found any results
if [[ ! -s "$TEMP_FILE" ]]; then
    echo -e "${RED}No app-template charts found in the specified files.${NC}"
    rm "$TEMP_FILE"
    exit 1
fi

# Sort and group by version
echo -e "${GREEN}Summary of app-template versions:${NC}"
echo ""

# Get unique versions and count
declare -A version_counts=()
while IFS='|' read -r version file; do
    if [[ -n "$version" && "$version" != "N/A" ]]; then
        if [[ -z "${version_counts[$version]:-}" ]]; then
            version_counts[$version]=1
        else
            ((version_counts[$version]++))
        fi
    fi
done < "$TEMP_FILE"

# Display summary counts
if [[ ${#version_counts[@]} -gt 0 ]]; then
    echo -e "${BLUE}Version Distribution:${NC}"
    for version in $(printf '%s\n' "${!version_counts[@]}" | sort -V); do
        count=${version_counts[$version]}
        echo -e "  ${GREEN}$version${NC}: $count release(s)"
    done
    echo ""
else
    echo -e "${RED}No versions found in temp file.${NC}"
    cat "$TEMP_FILE"
    rm "$TEMP_FILE"
    exit 1
fi

# Group by major.minor version
echo -e "${BLUE}==================================================================${NC}"
echo -e "${BLUE}  Detailed Breakdown by Version${NC}"
echo -e "${BLUE}==================================================================${NC}"
echo ""

# Sort by version and display grouped results
current_version=""
count=0
while IFS='|' read -r version file; do
    if [[ "$version" != "$current_version" ]]; then
        if [[ -n "$current_version" ]]; then
            echo ""
        fi
        current_version="$version"
        count=0
        echo -e "${YELLOW}Version: $version${NC}"
        echo -e "${YELLOW}$(printf '=%.0s' {1..60})${NC}"
    fi
    ((count++))
    # Extract app name from path
    app_name=$(echo "$file" | awk -F'/' '{print $(NF-2)}')
    echo -e "  ${count}. ${GREEN}$app_name${NC}"
    echo -e "     ${BLUE}$file${NC}"
done < <(sort -V -t'|' -k1 "$TEMP_FILE")

echo ""
echo -e "${BLUE}==================================================================${NC}"
echo -e "${GREEN}Analysis complete!${NC}"
echo -e "${BLUE}==================================================================${NC}"

# Cleanup
rm "$TEMP_FILE"