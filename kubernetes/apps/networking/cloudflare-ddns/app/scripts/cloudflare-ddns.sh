#!/usr/bin/env bash

# Robust Bash Scripting
set -o nounset
set -o errexit
set -o pipefail

# ---------------------------------------------------------------------------
# Multi-domain Cloudflare DDNS
#
# Maintains A records pointing at the current public IPv4 for an arbitrary
# list of (zone, record_name) pairs across one or more Cloudflare zones.
#
# Required environment:
#   CLOUDFLARE_TOKEN     Cloudflare API token. Must have Zone.DNS:Edit on
#                        every zone listed in CLOUDFLARE_RECORDS.
#   CLOUDFLARE_RECORDS   Comma-separated list of "zone=record_name" pairs.
#                        record_name MUST be the FQDN (including the zone).
#                        Wildcards (*.example.com) are valid record_names.
#
#                        Example:
#                          example.com=example.com,example.com=*.example.com,\
#                          safespaces.dev=safespaces.dev,safespaces.dev=*.safespaces.dev
#
#   PUSHOVER_USER_KEY    Pushover credentials (optional notification).
#   PUSHOVER_TOKEN
#
# Legacy single-domain mode (CLOUDFLARE_DOMAIN only) is still supported and
# is converted to a CLOUDFLARE_RECORDS of "<domain>=<domain>" on the fly.
#
# Behavior:
#   - For each (zone, record_name):
#       * Look up the zone id.
#       * Look up the existing A record for record_name.
#       * If absent, CREATE it pointing at the current public IPv4.
#       * If present and content differs, UPDATE it.
#       * If present and content matches, skip.
#   - Errors against a single record DO NOT abort the rest of the run; they
#     are accumulated and reported at the end. A non-zero exit code is
#     returned if any record failed.
# ---------------------------------------------------------------------------

log() {
    echo "$(date -u) - $1" >&2
}

error_exit() {
    log "Error: $1"
    exit 1
}

# Retry a command with exponential backoff. The command is invoked as
# `"$@"` so any quoting in the caller's argv is preserved.
retry() {
    local max_attempts=3
    local delay=2
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        log "Attempt $attempt/$max_attempts: $*"
        if "$@"; then
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

pushover_notify() {
    local title="$1"
    local message="$2"
    # Best-effort notification. Failure to notify is logged but never fatal.
    if [[ -z "${PUSHOVER_TOKEN:-}" || -z "${PUSHOVER_USER_KEY:-}" ]]; then
        log "Pushover credentials not set; skipping notification: $title"
        return 0
    fi
    curl -s \
        --form-string "token=$PUSHOVER_TOKEN" \
        --form-string "user=$PUSHOVER_USER_KEY" \
        --form-string "message=$message" \
        --form-string "title=$title" \
        https://api.pushover.net/1/messages.json >/dev/null || \
        log "Pushover notification failed for: $title"
}

# Resolve current public IPv4. Errors here are fatal because nothing
# else can proceed without it.
current_ipv4="$(retry curl -fsS https://ipv4.icanhazip.com/)" \
    || error_exit "Failed to fetch current IPv4 address after multiple attempts"
current_ipv4="${current_ipv4//$'\n'/}"
if [[ ! "$current_ipv4" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    error_exit "Fetched IPv4 is not a valid IPv4 address: '$current_ipv4'"
fi
log "Fetched current IP Address: $current_ipv4"

# Build the list of (zone, record) pairs to manage.
declare -a TARGETS=()
if [[ -n "${CLOUDFLARE_RECORDS:-}" ]]; then
    # Split on comma. We allow whitespace around tokens.
    IFS=',' read -r -a _raw <<<"$CLOUDFLARE_RECORDS"
    for entry in "${_raw[@]}"; do
        # Trim surrounding whitespace.
        entry="${entry#"${entry%%[![:space:]]*}"}"
        entry="${entry%"${entry##*[![:space:]]}"}"
        [[ -z "$entry" ]] && continue
        if [[ "$entry" != *"="* ]]; then
            log "Skipping malformed CLOUDFLARE_RECORDS entry (missing '='): '$entry'"
            continue
        fi
        TARGETS+=("$entry")
    done
elif [[ -n "${CLOUDFLARE_DOMAIN:-}" ]]; then
    # Backwards-compatible single-domain mode.
    log "CLOUDFLARE_RECORDS not set; using legacy CLOUDFLARE_DOMAIN=$CLOUDFLARE_DOMAIN"
    TARGETS+=("$CLOUDFLARE_DOMAIN=$CLOUDFLARE_DOMAIN")
fi

if [[ ${#TARGETS[@]} -eq 0 ]]; then
    error_exit "No DNS targets configured. Set CLOUDFLARE_RECORDS (preferred) or CLOUDFLARE_DOMAIN."
fi

# Cache zone -> zone_id lookups so we don't refetch.
declare -A ZONE_IDS=()

resolve_zone_id() {
    local zone="$1"
    if [[ -n "${ZONE_IDS[$zone]:-}" ]]; then
        echo "${ZONE_IDS[$zone]}"
        return 0
    fi
    local resp
    resp=$(retry curl -fsS -X GET \
        "https://api.cloudflare.com/client/v4/zones?name=$zone&status=active" \
        -H "Authorization: Bearer $CLOUDFLARE_TOKEN" \
        -H "Content-Type: application/json") || return 1
    local zid
    zid=$(echo "$resp" | jq --raw-output '.result[0].id // empty')
    if [[ -z "$zid" || "$zid" == "null" ]]; then
        log "Zone lookup returned no result for '$zone'. Response: $resp"
        return 1
    fi
    ZONE_IDS[$zone]="$zid"
    echo "$zid"
}

# Returns the JSON record object (first match) or empty string if no record exists.
get_record() {
    local zone_id="$1"
    local record_name="$2"
    # The API requires the record name URL-encoded for safety, but jq handles
    # quoting. Wildcards (*) are accepted as-is by the API.
    local resp
    resp=$(retry curl -fsS -G \
        "https://api.cloudflare.com/client/v4/zones/$zone_id/dns_records" \
        --data-urlencode "type=A" \
        --data-urlencode "name=$record_name" \
        -H "Authorization: Bearer $CLOUDFLARE_TOKEN" \
        -H "Content-Type: application/json") || return 1
    echo "$resp" | jq -c '.result[0] // empty'
}

create_record() {
    local zone_id="$1"
    local record_name="$2"
    local ip="$3"
    local payload
    payload=$(jq -nc \
        --arg name "$record_name" \
        --arg content "$ip" \
        '{type:"A",name:$name,content:$content,proxied:false,ttl:1}')
    retry curl -fsS -X POST \
        "https://api.cloudflare.com/client/v4/zones/$zone_id/dns_records" \
        -H "Authorization: Bearer $CLOUDFLARE_TOKEN" \
        -H "Content-Type: application/json" \
        --data "$payload"
}

update_record() {
    local zone_id="$1"
    local record_id="$2"
    local record_name="$3"
    local ip="$4"
    local payload
    payload=$(jq -nc \
        --arg name "$record_name" \
        --arg content "$ip" \
        '{type:"A",name:$name,content:$content,proxied:false,ttl:1}')
    retry curl -fsS -X PUT \
        "https://api.cloudflare.com/client/v4/zones/$zone_id/dns_records/$record_id" \
        -H "Authorization: Bearer $CLOUDFLARE_TOKEN" \
        -H "Content-Type: application/json" \
        --data "$payload"
}

# Accumulators for the end-of-run summary.
declare -a UPDATED=()
declare -a CREATED=()
declare -a UNCHANGED=()
declare -a FAILED=()

for entry in "${TARGETS[@]}"; do
    zone="${entry%%=*}"
    record_name="${entry#*=}"

    log "--- Processing zone='$zone' record='$record_name' ---"

    if ! zone_id="$(resolve_zone_id "$zone")"; then
        log "Failed to resolve zone id for '$zone'"
        FAILED+=("$record_name (zone lookup failed)")
        continue
    fi
    log "Resolved zone id for $zone: $zone_id"

    if ! existing="$(get_record "$zone_id" "$record_name")"; then
        log "Failed to fetch existing record for '$record_name'"
        FAILED+=("$record_name (lookup failed)")
        continue
    fi

    if [[ -z "$existing" ]]; then
        log "Record '$record_name' does not exist; creating with IP $current_ipv4"
        if resp="$(create_record "$zone_id" "$record_name" "$current_ipv4")"; then
            if [[ "$(echo "$resp" | jq -r '.success')" == "true" ]]; then
                log "Created '$record_name' -> $current_ipv4"
                CREATED+=("$record_name -> $current_ipv4")
            else
                log "Create returned success=false for '$record_name': $resp"
                FAILED+=("$record_name (create returned failure)")
            fi
        else
            log "Create API call failed for '$record_name'"
            FAILED+=("$record_name (create API call failed)")
        fi
        continue
    fi

    record_id="$(echo "$existing" | jq -r '.id')"
    old_ip="$(echo "$existing" | jq -r '.content')"
    log "Existing record '$record_name' id=$record_id content=$old_ip"

    if [[ "$old_ip" == "$current_ipv4" ]]; then
        log "No change for '$record_name' (already $current_ipv4)"
        UNCHANGED+=("$record_name")
        continue
    fi

    log "Updating '$record_name' $old_ip -> $current_ipv4"
    if resp="$(update_record "$zone_id" "$record_id" "$record_name" "$current_ipv4")"; then
        if [[ "$(echo "$resp" | jq -r '.success')" == "true" ]]; then
            log "Updated '$record_name' to $current_ipv4"
            UPDATED+=("$record_name: $old_ip -> $current_ipv4")
        else
            log "Update returned success=false for '$record_name': $resp"
            FAILED+=("$record_name (update returned failure)")
        fi
    else
        log "Update API call failed for '$record_name'"
        FAILED+=("$record_name (update API call failed)")
    fi
done

# Build summary.
summary=""
[[ ${#CREATED[@]}   -gt 0 ]] && summary+="Created:"$'\n'"$(printf '  - %s\n' "${CREATED[@]}")"$'\n'
[[ ${#UPDATED[@]}   -gt 0 ]] && summary+="Updated:"$'\n'"$(printf '  - %s\n' "${UPDATED[@]}")"$'\n'
[[ ${#UNCHANGED[@]} -gt 0 ]] && summary+="Unchanged:"$'\n'"$(printf '  - %s\n' "${UNCHANGED[@]}")"$'\n'
[[ ${#FAILED[@]}    -gt 0 ]] && summary+="Failed:"$'\n'"$(printf '  - %s\n' "${FAILED[@]}")"$'\n'

log "Summary:"$'\n'"$summary"

# Notify only when something actually changed or something failed.
if [[ ${#CREATED[@]} -gt 0 || ${#UPDATED[@]} -gt 0 ]]; then
    title="Cloudflare DDNS — records changed (IP $current_ipv4)"
    pushover_notify "$title" "$summary"
fi
if [[ ${#FAILED[@]} -gt 0 ]]; then
    title="Cloudflare DDNS — failures (IP $current_ipv4)"
    pushover_notify "$title" "$summary"
    exit 1
fi

exit 0
