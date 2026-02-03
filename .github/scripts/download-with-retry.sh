#!/bin/bash
# Download helper script with retry logic for external services
# Usage: download-with-retry.sh <url> [output-file] [description]

set -e

URL="${1}"
OUTPUT_FILE="${2}"
DESCRIPTION="${3:-download}"
MAX_RETRIES=5
INITIAL_DELAY=5
MAX_DELAY=60

function log() {
    echo "[download-with-retry] $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

function download_with_retry() {
    local attempt=1
    local delay=$INITIAL_DELAY

    while [ $attempt -le $MAX_RETRIES ]; do
        log "Attempt $attempt/$MAX_RETRIES: $DESCRIPTION from $URL"
        
        if [ -n "$OUTPUT_FILE" ]; then
            if curl -fsSL --retry 3 --retry-delay 2 --connect-timeout 10 --max-time 30 "$URL" -o "$OUTPUT_FILE"; then
                log "Successfully downloaded $DESCRIPTION"
                return 0
            fi
        else
            if curl -fsSL --retry 3 --retry-delay 2 --connect-timeout 10 --max-time 30 "$URL" | bash; then
                log "Successfully downloaded and executed $DESCRIPTION"
                return 0
            fi
        fi
        
        if [ $attempt -lt $MAX_RETRIES ]; then
            log "Failed, retrying in ${delay}s..."
            sleep $delay
            delay=$((delay * 2))
            if [ $delay -gt $MAX_DELAY ]; then
                delay=$MAX_DELAY
            fi
        fi
        
        attempt=$((attempt + 1))
    done
    
    log "Failed to download $DESCRIPTION after $MAX_RETRIES attempts"
    log "URL was: $URL"
    return 1
}

if [ -z "$URL" ]; then
    log "Error: No URL provided"
    echo "Usage: $0 <url> [output-file] [description]"
    exit 1
fi

download_with_retry
