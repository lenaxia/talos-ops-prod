#!/usr/bin/env bash

# Robust Bash Scripting
set -o nounset
set -o errexit
set -o pipefail

# Function to log messages
log() {
    echo "$(date -u) - $1"
}

# Function to exit in case of an error
error_exit() {
    log "Error: $1"
    exit 1
}

# Function to retry a command with backoff
retry() {
    local max_attempts=3
    local delay=2
    local attempt=1
    local cmd="$1"
    shift
    
    while [ $attempt -le $max_attempts ]; do
        log "Attempt $attempt/$max_attempts: $cmd"
        if "$cmd" "$@"; then
            return 0
        fi
        if [ $attempt -lt $max_attempts ]; then
            log "Command failed, retrying in ${delay}s..."
            sleep $delay
            delay=$((delay * 2))
        fi
        attempt=$((attempt + 1))
    done
    return 1
}

# Fetch Current External IP
current_ipv4="$(retry curl -s https://ipv4.icanhazip.com/)" || error_exit "Failed to fetch current IPv4 address after multiple attempts"

log "Fetched current IP Address: $current_ipv4"

# Fetch Cloudflare Zone ID
zone_id=$(retry curl -s -X GET \
    "https://api.cloudflare.com/client/v4/zones?name=$CLOUDFLARE_DOMAIN&status=active" \
    -H "Authorization: Bearer $CLOUDFLARE_TOKEN" \
    -H "Content-Type: application/json" \
    | jq --raw-output ".result[0] | .id") || error_exit "Failed to fetch Cloudflare Zone ID after multiple attempts"


log "Fetched zone id: $zone_id"

# Fetch Current DNS Record
record_ipv4=$(retry curl -s -X GET \
    "https://api.cloudflare.com/client/v4/zones/$zone_id/dns_records?name=$CLOUDFLARE_DOMAIN&type=A" \
    -H "Authorization: Bearer $CLOUDFLARE_TOKEN" \
    -H "Content-Type: application/json") || error_exit "Failed to fetch current DNS record after multiple attempts"

log "ipv4 record $record_ipv4"

old_ipv4=$(echo "$record_ipv4" | jq --raw-output '.result[0] | .content' || error_exit "Failed to parse current DNS record")

log "Fetched old IP $old_ipv4 from record"

# Compare IPs and Update if Different
if [[ "$current_ipv4" == "$old_ipv4" ]]; then
    log "IP Address '$current_ipv4' has not changed $old_ipv4"
    exit 0
fi

record_ipv4_identifier="$(echo "$record_ipv4" | jq --raw-output '.result[0] | .id' || error_exit "Failed to parse DNS record identifier")"

log "Fetched ipv4 identifier $record_ipv4_identifier"

# Update DNS Record
update_ipv4=$(retry curl -s -X PUT \
    "https://api.cloudflare.com/client/v4/zones/$zone_id/dns_records/$record_ipv4_identifier" \
    -H "Authorization: Bearer $CLOUDFLARE_TOKEN" \
    -H "Content-Type: application/json" \
    --data "{\"id\":\"$zone_id\",\"type\":\"A\",\"proxied\":false,\"name\":\"$CLOUDFLARE_DOMAIN\",\"content\":\"$current_ipv4\"}") || error_exit "Failed to update DNS record after multiple attempts"

if [[ "$(echo "$update_ipv4" | jq --raw-output '.success')" == "true" ]]; then
    log "Success - IP Address '$current_ipv4' has been updated"
    pushover_result=$(curl -s \
        --form-string "token=$PUSHOVER_TOKEN" \
        --form-string "user=$PUSHOVER_USER_KEY" \
        --form-string "message=IP Address for $CLOUDFLARE_DOMAIN has been updated to $current_ipv4" \
        --form-string "title=IP Address Updated - $CLOUDFLARE_DOMAIN" \
        https://api.pushover.net/1/messages.json)
else
    pushover_result=$(curl -s \
        --form-string "token=$PUSHOVER_TOKEN" \
        --form-string "user=$PUSHOVER_USER_KEY" \
        --form-string "message=Failed to update IP address for  $CLOUDFLARE_DOMAIN - Error Response: $update_ipv4" \
        --form-string "title=IP Address Failed - $CLOUDFLARE_DOMAIN" \
        https://api.pushover.net/1/messages.json)
    error_exit "Updating IP Address '$current_ipv4' has failed"
fi

