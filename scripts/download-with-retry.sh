#!/bin/bash
# Wrapper script for downloading tools with retry logic and better error handling

set -euo pipefail

# Configuration
MAX_RETRIES=5
RETRY_DELAY=5
TIMEOUT=60

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Log function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" >&2
}

# Download function with retry logic
download_with_retry() {
    local url="$1"
    local attempt=0

    log "Attempting to download: ${url}"

    while [ $attempt -lt $MAX_RETRIES ]; do
        attempt=$((attempt + 1))
        
        if curl -fsSL --max-time $TIMEOUT "$url"; then
            log "Download successful on attempt ${attempt}/${MAX_RETRIES}"
            return 0
        else
            local exit_code=$?
            
            if [ $attempt -lt $MAX_RETRIES ]; then
                warn "Download failed (attempt ${attempt}/${MAX_RETRIES}, exit code: ${exit_code})"
                warn "Retrying in ${RETRY_DELAY} seconds..."
                sleep $RETRY_DELAY
            else
                error "Download failed after ${MAX_RETRIES} attempts"
                error "URL: ${url}"
                error "Exit code: ${exit_code}"
                error ""
                error "Possible causes:"
                error "  1. The external service is temporarily unavailable"
                error "  2. Network connectivity issues"
                error "  3. Service is rate-limiting requests"
                error ""
                error "Suggestions:"
                error "  - Wait a few minutes and retry"
                error "  - Check if you can access the URL manually: ${url}"
                error "  - Try running the workflow again later"
                return 1
            fi
        fi
    done
}

# Main execution
if [ $# -eq 0 ]; then
    error "Usage: $0 <url>"
    exit 1
fi

download_with_retry "$1"
