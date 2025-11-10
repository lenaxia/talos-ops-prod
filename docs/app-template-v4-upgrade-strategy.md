
# App-Template v4.3.0 Upgrade Strategy

**Document Version:** 1.0  
**Date:** 2025-11-08  
**Author:** Infrastructure Team  
**Status:** Draft for Review

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Pre-Upgrade Checklist](#pre-upgrade-checklist)
3. [Upgrade Approach](#upgrade-approach)
4. [Technical Changes Required](#technical-changes-required)
5. [Implementation Plan](#implementation-plan)
6. [Post-Upgrade Validation](#post-upgrade-validation)
7. [Risk Mitigation](#risk-mitigation)
8. [Appendix: Release Examples](#appendix-release-examples)

---

## Executive Summary

### Scope

This document outlines the strategy for upgrading 32 helm releases using the bjw-s app-template chart from various v3.x versions to v4.3.0.

**Current Version Distribution:**
- 1 release on v2.6.0 (magicmirror - requires special handling)
- 22 releases on v3.1.0
- 2 releases on v3.3.1
- 1 release on v3.3.2
- 1 release on v3.4.0
- 1 release on v3.5.1
- 1 release on v3.6.0
- 3 releases on v3.7.3

**Target Version:** 4.3.0 (latest stable as of this document)

### Risk Assessment

**Overall Risk Level:** LOW to MEDIUM

The v3→v4 upgrade is significantly simpler than previous major version upgrades (v1→v2, v2→v3) because:

1. **Structural Compatibility:** The YAML structure remains largely compatible between v3 and v4
2. **Automatic Handling:** Most changes are handled automatically by the chart itself
3. **Minimal Transformations:** Only the chart version number needs to be updated in most cases
4. **Proven Track Record:** PR #410 (app-template 4.3.0 → 4.4.0) was successfully merged, indicating v4.x stability

**Key Risk Factors:**
- Resource naming changes may trigger pod recreation (expected and manageable)
- One release (magicmirror) on v2.6.0 requires v2→v3→v4 multi-step upgrade
- ServiceAccount static token behavior change may affect applications relying on this feature
- Label changes are transparent but may affect external monitoring/alerting rules

### Timeline Estimate

**Total Estimated Time:** 2-3 days

- **Day 1:** Preparation, script development, testing (4-6 hours)
- **Day 2:** Phased rollout of v3.x→v4.3.0 upgrades (4-6 hours)
- **Day 3:** Special handling for magicmirror v2.6.0→v4.3.0, validation (2-4 hours)

**Recommended Schedule:**
- Execute during maintenance window
- Stagger upgrades across application categories
- Allow 15-30 minutes between batches for observation

---

## Pre-Upgrade Checklist

### 1. Backup Recommendations

#### Critical Backups
- [ ] **Flux GitOps Repository:** Ensure git repository is committed and pushed
- [ ] **Persistent Volume Claims:** Backup PVCs for stateful applications
  - Priority: databases, media servers, configuration stores
  - Use Kopia or Velero for automated backups
- [ ] **Kubernetes Resources:** Export current HelmRelease manifests
  ```bash
  kubectl get helmrelease -A -o yaml > helmreleases-backup-$(date +%Y%m%d).yaml
  ```

#### Recommended Backups
- [ ] **Application Configurations:** Export ConfigMaps and Secrets
- [ ] **Ingress Configurations:** Document current ingress endpoints
- [ ] **Service Endpoints:** Record LoadBalancer IPs and NodePorts

### 2. Validation Steps

#### Environment Validation
- [ ] Verify Flux is healthy and reconciling
  ```bash
  flux check
  flux get sources helm -A
  ```
- [ ] Confirm bjw-s Helm repository is accessible
  ```bash
  kubectl get helmrepository bjw-s -n flux-system
  ```
- [ ] Check cluster health and available resources
  ```bash
  kubectl top nodes
  kubectl get nodes
  ```

#### Application Validation
- [ ] Document current application states
  ```bash
  kubectl get helmrelease -A | grep app-template
  ```
- [ ] Verify all applications are running and healthy
- [ ] Test critical application functionality
- [ ] Document current ingress URLs and access methods

#### Monitoring Setup
- [ ] Ensure Prometheus/Grafana are operational
- [ ] Set up alerts for pod restarts and failures
- [ ] Prepare log aggregation (Loki/Vector) for troubleshooting

### 3. Prerequisites

#### Technical Requirements
- [ ] Kubernetes cluster version: 1.24+ (verify compatibility)
- [ ] Flux version: v2.0.0+ (verify compatibility)
- [ ] Helm version: 3.8+ (used by Flux)
- [ ] kubectl access with cluster-admin privileges

#### Team Requirements
- [ ] Primary operator available for execution
- [ ] Secondary operator available for validation
- [ ] Communication channel established (Slack/Teams)
- [ ] Rollback plan reviewed and understood

#### Documentation Requirements
- [ ] This strategy document reviewed and approved
- [ ] Runbook prepared for common issues
- [ ] Contact information for application owners
- [ ] Escalation path defined

---

## Upgrade Approach

### Phased Rollout Strategy

The upgrade will be executed in phases to minimize risk and allow for early detection of issues.

#### Phase 1: Canary Release (Low-Risk Applications)
**Target:** 2-3 non-critical applications  
**Duration:** 30-60 minutes  
**Purpose:** Validate upgrade process and identify unexpected issues

**Candidates:**
- [`imaginary`](kubernetes/apps/media/imaginary/app/helm-release.yaml) - Simple stateless image processing service
- [`librespeed`](kubernetes/apps/utilities/librespeed/app/helm-release.yaml) - Speed test utility
- [`webfinger`](kubernetes/apps/networking/webfinger/app/helm-release.yaml) - Simple networking utility

**Success Criteria:**
- Applications deploy successfully
- Pods reach Running state
- Ingress endpoints remain accessible
- No unexpected errors in logs

#### Phase 2: Stateless Applications
**Target:** 15-18 stateless applications  
**Duration:** 2-3 hours  
**Batch Size:** 3-5 applications per batch

**Categories:**
- Media utilities (metube, subgen)
- Home automation clients (browserless, changedetection)
- Development tools (code-server, pgadmin)
- Networking services (cloudflare-ddns)

**Approach:**
- Process in batches of 3-5 applications
- Wait 15 minutes between batches
- Monitor for pod restarts and errors

#### Phase 3: Stateful Applications
**Target:** 10-12 stateful applications  
**Duration:** 2-3 hours  
**Batch Size:** 2-3 applications per batch

**Categories:**
- Media servers (plex, jellyfin, tautulli)
- Media management (*arr stack: radarr, sonarr, bazarr)
- Home automation (frigate, esphome, mosquitto)
- Data services (redis, openldap)

**Approach:**
- Process in smaller batches (2-3 applications)
- Wait 20-30 minutes between batches
- Verify data persistence after upgrade
- Test application functionality

#### Phase 4: Critical Infrastructure
**Target:** 3-4 critical applications  
**Duration:** 1-2 hours  
**Individual Processing:** One at a time

**Applications:**
- [`mosquitto`](kubernetes/apps/home/mosquitto/app/helm-release.yaml) - MQTT broker (dependency for other services)
- [`redis`](kubernetes/apps/databases/redis/app/helm-release.yaml) - Cache/session store
- Any application with external dependencies

**Approach:**
- Upgrade one application at a time
- Full validation before proceeding to next
- Monitor dependent services

#### Phase 5: Special Cases
**Target:** magicmirror (v2.6.0)  
**Duration:** 1-2 hours  
**Approach:** Multi-step upgrade (v2→v3→v4)

### Testing Methodology

#### Per-Application Testing
After each application upgrade:

1. **Deployment Verification**
   ```bash
   kubectl get helmrelease <app-name> -n <namespace>
   kubectl get pods -n <namespace> -l app.kubernetes.io/name=<app-name>
   ```

2. **Health Check**
   ```bash
   kubectl describe pod -n <namespace> <pod-name>
   kubectl logs -n <namespace> <pod-name> --tail=50
   ```

3. **Functional Testing**
   - Access application via ingress URL
   - Verify core functionality
   - Check data persistence (for stateful apps)

4. **Performance Check**
   - Monitor resource usage
   - Check response times
   - Verify no memory leaks

#### Batch Testing
After each batch:

1. **Cluster Health**
   ```bash
   kubectl get nodes
   kubectl top nodes
   kubectl get events --sort-by='.lastTimestamp' | head -20
   ```

2. **Flux Reconciliation**
   ```bash
   flux get helmreleases -A
   flux logs --level=error
   ```

3. **Service Availability**
   - Test ingress endpoints
   - Verify service discovery
   - Check inter-service communication

### Rollback Plan

#### Immediate Rollback (Per-Application)
If an application fails to deploy or function:

1. **Revert Chart Version**
   ```bash
   # Edit helm-release.yaml
   git checkout HEAD -- kubernetes/apps/<category>/<app>/app/helm-release.yaml
   git commit -m "Rollback <app> to v3.x"
   git push
   ```

2. **Force Reconciliation**
   ```bash
   flux reconcile helmrelease <app-name> -n <namespace>
   ```

3. **Verify Rollback**
   ```bash
   kubectl get helmrelease <app-name> -n <namespace>
   kubectl get pods -n <namespace>
   ```

#### Batch Rollback
If multiple applications in a batch fail:

1. **Pause Flux Reconciliation**
   ```bash
   flux suspend helmrelease <app-name> -n <namespace>
   ```

2. **Revert Git Changes**
   ```bash
   git revert <commit-hash>
   git push
   ```

3. **Resume Reconciliation**
   ```bash
   flux resume helmrelease <app-name> -n <namespace>
   ```

#### Full Rollback
If systemic issues are discovered:

1. **Suspend All Upgrades**
   ```bash
   flux suspend kustomization apps
   ```

2. **Revert All Changes**
   ```bash
   git revert <commit-range>
   git push
   ```

3. **Resume with Validation**
   ```bash
   flux resume kustomization apps
   # Monitor closely
   ```

---

## Technical Changes Required

### Breaking Changes Identified

#### 1. Chart Version Update (Required)
**Change:** Update chart version from 3.x to 4.3.0  
**Impact:** All 32 releases  
**Risk:** Low - handled automatically by Helm

**Before:**
```yaml
spec:
  chart:
    spec:
      chart: app-template
      version: 3.1.0  # or 3.3.1, 3.4.0, etc.
```

**After:**
```yaml
spec:
  chart:
    spec:
      chart: app-template
      version: 4.3.0
```

#### 2. Resource Naming Changes (Automatic)
**Change:** Resource names may be regenerated  
**Impact:** Pods will be recreated, services may get new endpoints  
**Risk:** Low - Kubernetes handles gracefully via rolling updates

**Behavior:**
- Deployments: Rolling update (zero downtime)
- StatefulSets: Ordered recreation (brief downtime per pod)
- Services: Endpoint updates (transparent to clients)
- Ingress: No changes expected

**Note:** This is handled automatically by Kubernetes and Flux. No manual intervention required.

#### 3. Label Changes (Transparent)
**Change:** `app.kubernetes.io/component` → `app.kubernetes.io/controller`  
**Impact:** Monitoring, alerting, and label selectors  
**Risk:** Low - transparent to most use cases

**Before:**
```yaml
metadata:
  labels:
    app.kubernetes.io/component: main
```

**After:**
```yaml
metadata:
  labels:
    app.kubernetes.io/controller: main
```

**Action Required:**
- Review Prometheus/Grafana dashboards for label-based queries
- Update any custom monitoring rules using `app.kubernetes.io/component`
- Verify ServiceMonitor and PodMonitor configurations

#### 4. ServiceAccount Static Tokens (Behavioral Change)
**Change:** Static tokens no longer created by default  
**Impact:** Applications relying on automatic token creation  
**Risk:** Medium - may break applications expecting tokens

**Affected Applications:** Unknown (requires audit)

**Detection:**
```bash
# Check for ServiceAccount usage
kubectl get serviceaccount -A
# Check for token mounts
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.serviceAccountName}{"\n"}{end}'
```

**Mitigation:**
- Audit applications for ServiceAccount token usage
- Manually create tokens if needed
- Use projected volume tokens (recommended)

### Optional Optimizations

These changes are not required but improve configuration clarity and reduce redundancy.

#### 1. Remove Redundant `controller` Field from Services
**Applicable:** Services with only one controller  
**Benefit:** Cleaner configuration  
**Risk:** None - backward compatible

**Before:**
```yaml
service:
  main:
    controller: main  # Redundant if only one controller
    ports:
      http:
        port: 8080
```

**After:**
```yaml
service:
  main:
    # controller field omitted - defaults to main
    ports:
      http:
        port: 8080
```

**Recommendation:** Apply during upgrade for cleaner configs

#### 2. Remove Redundant `service.identifier` from Ingress Paths
**Applicable:** Ingress paths with only one service  
**Benefit:** Cleaner configuration  
**Risk:** None - backward compatible

**Before:**
```yaml
ingress:
  main:
    hosts:
      - host: app.example.com
        paths:
          - path: /
            service:
              identifier: main  # Redundant if only one service
              port: http
```

**After:**
```yaml
ingress:
  main:
    hosts:
      - host: app.example.com
        paths:
          - path: /
            service:
              # identifier omitted - defaults to main
              port: http
```

**Recommendation:** Apply during upgrade for cleaner configs

### Special Case: magicmirror (v2.6.0 → v4.3.0)

The magicmirror release requires a multi-step upgrade due to the large version gap.

#### Step 1: v2.6.0 → v3.1.0
**Major Changes:**
- `controller` → `controllers.main`
- `image` → `controllers.main.containers.main.image`
- `service` structure changes
- `ingress` structure changes
- `persistence` structure changes

**Approach:** Use existing [`app-template-upgrade-v2-ruamel.py`](hack/app-template-upgrade-v2-ruamel.py) script

#### Step 2: v3.1.0 → v4.3.0
**Major Changes:**
- Chart version update only
- Minimal structural changes

**Approach:** Standard upgrade process (same as other v3.x releases)

#### Detailed Migration Plan

**Current State Analysis:**
```yaml
# magicmirror v2.6.0 structure
controllers:
  main:
    type: statefulset
    initContainers:
      install-modules:
        # Complex init container with volume mounts
    containers:
      main:
        image:
          repository: karsten13/magicmirror
          tag: v2.33.0
    statefulset:
      volumeClaimTemplates:
        - name: modules
          # PVC configuration
```

**Migration Steps:**

1. **Backup Current Configuration**
   ```bash
   kubectl get helmrelease magicmirror -n home -o yaml > magicmirror-v2-backup.yaml
   kubectl get pvc -n home -l app.kubernetes.io/name=magicmirror -o yaml > magicmirror-pvc-backup.yaml
   ```

2. **Upgrade to v3.1.0**
   - Run v2→v3 upgrade script
   - Verify structure transformation
   - Test deployment
   - Validate functionality

3. **Upgrade to v4.3.0**
   - Update chart version
   - Apply standard v3→v4 changes
   - Test deployment
   - Validate functionality

**Risk Mitigation:**
- Perform during low-usage period
- Keep v2.6.0 backup for quick rollback
- Test init container functionality thoroughly
- Verify module persistence

---

## Implementation Plan

### Script Requirements

#### Primary Upgrade Script: `app-template-upgrade-v4.py`

**Purpose:** Automate v3.x → v4.3.0 upgrades

**Features:**
- Scan directory for helm-release.yaml files
- Identify app-template charts on v3.x
- Update chart version to 4.3.0
- Apply optional optimizations (configurable)
- Preserve YAML formatting and comments
- Generate upgrade report

**Implementation:**
```python
#!/usr/bin/env python3
"""
App-Template v3.x to v4.3.0 Upgrade Script

This script automates the upgrade of bjw-s app-template helm releases
from v3.x to v4.3.0. The upgrade is minimal as v4 maintains backward
compatibility with v3 structure.

Usage:
    python app-template-upgrade-v4.py <directory> [options]

Options:
    -d, --directory     Directory to scan for helm releases
    -t, --target        Target version (default: 4.3.0)
    -o, --optimize      Apply optional optimizations
    -y, --yes           Auto-approve changes
    --dry-run           Show changes without applying
    --skip-version      Skip version check (process all)
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from ruamel.yaml import YAML

LOG = logging.getLogger('app-template-upgrade-v4')

HELM_RELEASE_NAMES = ["helmrelease.yaml", "helm-release.yaml"]
TARGET_VERSION = "4.3.0"

def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    LOG.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    LOG.addHandler(handler)

def load_yaml_file(filepath):
    yaml = YAML()
    yaml.preserve_quotes = True
    with open(filepath, 'r') as file:
        return yaml.load(file)

def save_yaml_file(filepath, data):
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    with open(filepath, 'w') as file:
        yaml.dump(data, file)

def get_nested_value(data, path):
    """Get nested value using dot notation path"""
    value = data
    for key in path.split('.'):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value

def should_process(filepath, data, skip_version_check=False):
    """Determine if helm release should be processed"""
    # Check if it's an app-template chart
    chart = get_nested_value(data, 'spec.chart.spec.chart')
    if chart != 'app-template':
        return False
    
    # Check version
    version = get_nested_value(data, 'spec.chart.spec.version')
    if version is None:
        LOG.warning(f"No version found in {filepath}")
        return False
    
    if skip_version_check:
        return True
    
    # Only process v3.x versions
    if version.startswith('3.'):
        return True
    
    if version.startswith('2.'):
        LOG.warning(f"Skipping {filepath} - v2.x requires multi-step upgrade")
        return False
    
    if version.startswith('4.'):
        LOG.info(f"Skipping {filepath} - already on v4.x")
        return False
    
    return False

def upgrade_release(filepath, data, target_version, optimize=False):
    """Upgrade helm release to target version"""
    current_version = get_nested_value(data, 'spec.chart.spec.version')
    
    LOG.info(f"Upgrading {filepath}: {current_version} → {target_version}")
    
    # Update chart version
    data['spec']['chart']['spec']['version'] = target_version
    
    # Apply optional optimizations
    if optimize:
        apply_optimizations(data)
    
    return data

def apply_optimizations(data):
    """Apply optional v4 optimizations"""
    values = get_nested_value(data, 'spec.values')
    if not values:
        return
    
    # Optimization 1: Remove redundant controller field from services
    services = values.get('service', {})
    controllers = values.get('controllers', {})
    
    if len(controllers) == 1:
        controller_name = next(iter(controllers))
        for service_name, service_config in services.items():
            if isinstance(service_config, dict):
                if service_config.get('controller') == controller_name:
                    LOG.debug(f"Removing redundant controller field from service {service_name}")
                    service_config.pop('controller', None)
    
    # Optimization 2: Remove redundant service identifier from ingress
    ingresses = values.get('ingress', {})
    if len(services) == 1:
        service_name = next(iter(services))
        for ingress_name, ingress_config in ingresses.items():
            if isinstance(ingress_config, dict):
                hosts = ingress_config.get('hosts', [])
                for host in hosts:
                    paths = host.get('paths', [])
                    for path in paths:
                        service_config = path.get('service', {})
                        if service_config.get('identifier') == service_name:
                            LOG.debug(f"Removing redundant service identifier from ingress {ingress_name}")
                            service_config.pop('identifier', None)

def main():
    parser = argparse.ArgumentParser(
        description='Upgrade app-template helm releases from v3.x to v4.3.0'
    )
    parser.add_argument(
        'directory',
        help='Directory to scan for helm releases'
    )
    parser.add_argument(
        '-t', '--target',
        default=TARGET_VERSION,
        help=f'Target version (default: {TARGET_VERSION})'
    )
    parser.add_argument(
        '-o', '--optimize',
        action='store_true',
        help='Apply optional optimizations'
    )
    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='Auto-approve all changes'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show changes without applying'
    )
    parser.add_argument(
        '--skip-version-check',
        action='store_true',
        help='Skip version check and process all releases'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    LOG.info(f"Scanning directory: {args.directory}")
    LOG.info(f"Target version: {args.target}")
    
    if args.dry_run:
        LOG.info("DRY RUN MODE - No changes will be applied")
    
    processed = []
    skipped = []
    errors = []
    
    # Walk directory tree
    for root, _, files in os.walk(args.directory):
        for file in files:
            if file not in HELM_RELEASE_NAMES:
                continue
            
            filepath = os.path.join(root, file)
            
            try:
                data = load_yaml_file(filepath)
            except Exception as exc:
                LOG.error(f"Failed to load {filepath}: {exc}")
                errors.append((filepath, str(exc)))
                continue
            
            if data.get('kind') != 'HelmRelease':
                continue
            
            if not should_process(filepath, data, args.skip_version_check):
                skipped.append(filepath)
                continue
            
            try:
                current_version = get_nested_value(data, 'spec.chart.spec.version')
                
                if not args.yes and not args.dry_run:
                    response = input(f"\nUpgrade {filepath} ({current_version} → {args.target})? [y/N] ")
                    if response.lower() != 'y':
                        LOG.info(f"Skipped by user: {filepath}")
                        skipped.append(filepath)
                        continue
                
                upgraded_data = upgrade_release(
                    filepath,
                    data,
                    args.target,
                    args.optimize
                )
                
                if not args.dry_run:
                    save_yaml_file(filepath, upgraded_data)
                    LOG.info(f"✓ Upgraded: {filepath}")
                else:
                    LOG.info(f"Would upgrade: {filepath}")
                
                processed.append((filepath, current_version, args.target))
                
            except Exception as exc:
                LOG.error(f"Failed to process {filepath}: {exc}", exc_info=True)
                errors.append((filepath, str(exc)))
    
    # Print summary
    print("\n" + "="*80)
    print("UPGRADE SUMMARY")
    print("="*80)
    print(f"\nProcessed: {len(processed)}")
    print(f"Skipped: {len(skipped)}")
    print(f"Errors: {len(errors)}")
    
    if processed:
        print("\n✓ Successfully Processed:")
        for filepath, old_ver, new_ver in processed:
            print(f"  - {filepath} ({old_ver} → {new_ver})")
    
    if errors:
        print("\n✗ Errors:")
        for filepath, error in errors:
            print(f"  - {filepath}: {error}")
    
    if args.dry_run:
        print("\nDRY RUN - No changes were applied")
    
    return 0 if not errors else 1

if __name__ == "__main__":
    sys.exit(main())
```

#### Validation Script: `validate-app-template-upgrades.sh`

**Purpose:** Validate upgrades and check application health

**Implementation:**
```bash
#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE_FILTER="${1:-}"
TIMEOUT=300  # 5 minutes

echo "App-Template v4 Upgrade Validation"
echo "===================================="
echo ""

# Function to check if a pod is ready
check_pod_ready() {
    local namespace=$1
    local app=$2
    local timeout=$3
    
    echo -n "Checking $namespace/$app... "
    
    local end_time=$((SECONDS + timeout))
    while [ $SECONDS -lt $end_time ]; do
        local ready=$(kubectl get pods -n "$namespace" -l "app.kubernetes.io/name=$app" \
            -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")
        
        if [ "$ready" = "True" ]; then
            echo -e "${GREEN}✓ Ready${NC}"
            return 0
        fi
        
        sleep 5
    done
    
    echo -e "${RED}✗ Not Ready (timeout)${NC}"
    return 1
}

# Function to check HelmRelease status
check_helmrelease() {
    local namespace=$1
    local name=$2
    
    local status=$(kubectl get helmrelease "$name" -n "$namespace" \
        -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
    
    if [ "$status" = "True" ]; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${RED}✗ ($status)${NC}"
        return 1
    fi
}

# Get all app-template HelmReleases
echo "Scanning for app-template HelmReleases..."
echo ""

releases=$(kubectl get helmrelease -A -o json | \
    jq -r '.items[] | select(.spec.chart.spec.chart == "app-template") | "\(.metadata.namespace) \(.metadata.name) \(.spec.chart.spec.version)"')

if [ -z "$releases" ]; then
    echo "No app-template HelmReleases found"
    exit 0
fi

# Parse and validate each release
total=0
ready=0
not_ready=0
v4_count=0

while IFS= read -r line; do
    namespace=$(echo "$line" | awk '{print $1}')
    name=$(echo "$line" | awk '{print $2}')
    version=$(echo "$line" | awk '{print $3}')
    
    # Skip if namespace filter is set and doesn't match
    if [ -n "$NAMESPACE_FILTER" ] && [ "$namespace" != "$NAMESPACE_FILTER" ]; then
        continue
    fi
    
    total=$((total + 1))
    
    # Check if upgraded to v4
    if [[ "$version" == 4.* ]]; then
        v4_count=$((v4_count + 1))
        version_status="${GREEN}v$version${NC}"
    else
        version_status="${YELLOW}v$version${NC}"
    fi
    
    # Check HelmRelease status
    printf "%-30s %-20s %-15s " "$namespace/$name" "$version_status" ""
    
    if check_helmrelease "$namespace" "$name"; then
        ready=$((ready + 1))
    else
        not_ready=$((not_ready + 1))
        
        # Show recent events for failed releases
        echo "  Recent events:"
        kubectl get events -n "$namespace" --field-selector involvedObject.name="$name" \
            --sort-by='.lastTimestamp' | tail -5 | sed 's/^/    /'
    fi
    
done <<< "$releases"

# Summary
echo ""
echo "===================================="
echo "Summary:"
echo "  Total releases: $total"
echo "  Ready: $ready"
echo "  Not ready: $not_ready"
echo "  Upgraded to v4: $v4_count / $total"
echo ""

if [ $not_ready -gt 0 ]; then
    echo -e "${RED}Some releases are not ready. Check logs for details.${NC}"
    exit 1
else
    echo -e "${GREEN}All releases are ready!${NC}"
    exit 0
fi
```

### Testing Strategy

#### Unit Testing
**Scope:** Script functionality

**Tests:**
1. YAML parsing and preservation
2. Version detection logic
3. Optimization application
4. Error handling

**Execution:**
```bash
# Test with sample files
python app-template-upgrade-v
4.py --dry-run kubernetes/apps/media/test-samples/
```

#### Integration Testing
**Scope:** End-to-end upgrade process

**Test Environment:**
- Dedicated test namespace
- Sample applications from each category
- Monitoring and logging enabled

**Test Cases:**
1. Stateless application upgrade
2. Stateful application upgrade
3. Application with ingress
4. Application with multiple services
5. Application with init containers
6. Rollback scenario

**Execution:**
```bash
# Create test namespace
kubectl create namespace app-template-test

# Deploy test applications
# ... (deploy sample apps)

# Run upgrade
python app-template-upgrade-v4.py kubernetes/apps/test/ --yes

# Validate
./validate-app-template-upgrades.sh app-template-test

# Cleanup
kubectl delete namespace app-template-test
```

#### Production Validation
**Scope:** Real-world upgrade validation

**Approach:**
1. Select 2-3 canary applications
2. Perform upgrade during low-traffic period
3. Monitor for 30-60 minutes
4. Validate functionality
5. Proceed with phased rollout if successful

### Validation Criteria

#### Deployment Success
- [ ] HelmRelease shows Ready status
- [ ] Pods reach Running state within 5 minutes
- [ ] No CrashLoopBackOff or Error states
- [ ] Resource limits respected

#### Functional Validation
- [ ] Application accessible via ingress
- [ ] Core functionality works
- [ ] Data persistence verified (stateful apps)
- [ ] Inter-service communication works

#### Performance Validation
- [ ] Response times within acceptable range
- [ ] Resource usage similar to pre-upgrade
- [ ] No memory leaks detected
- [ ] No excessive CPU usage

#### Monitoring Validation
- [ ] Prometheus metrics available
- [ ] Grafana dashboards functional
- [ ] Alerts not firing unexpectedly
- [ ] Logs flowing to aggregation system

---

## Post-Upgrade Validation

### Health Checks

#### Immediate Validation (Per Application)
Execute immediately after each application upgrade:

```bash
#!/bin/bash
APP_NAME="$1"
NAMESPACE="$2"

echo "Validating $APP_NAME in $NAMESPACE..."

# 1. Check HelmRelease status
echo "1. HelmRelease status:"
kubectl get helmrelease "$APP_NAME" -n "$NAMESPACE"

# 2. Check pod status
echo "2. Pod status:"
kubectl get pods -n "$NAMESPACE" -l "app.kubernetes.io/name=$APP_NAME"

# 3. Check recent events
echo "3. Recent events:"
kubectl get events -n "$NAMESPACE" --field-selector involvedObject.name="$APP_NAME" \
    --sort-by='.lastTimestamp' | tail -10

# 4. Check logs for errors
echo "4. Recent logs:"
kubectl logs -n "$NAMESPACE" -l "app.kubernetes.io/name=$APP_NAME" --tail=50 | grep -i error || echo "No errors found"

# 5. Test ingress (if applicable)
INGRESS_HOST=$(kubectl get ingress -n "$NAMESPACE" -l "app.kubernetes.io/name=$APP_NAME" \
    -o jsonpath='{.items[0].spec.rules[0].host}' 2>/dev/null)
if [ -n "$INGRESS_HOST" ]; then
    echo "5. Testing ingress: https://$INGRESS_HOST"
    curl -s -o /dev/null -w "%{http_code}" "https://$INGRESS_HOST" || echo "Ingress test failed"
fi
```

#### Batch Validation
Execute after each batch of upgrades:

```bash
# Check cluster health
kubectl get nodes
kubectl top nodes
kubectl get events --all-namespaces --sort-by='.lastTimestamp' | tail -20

# Check Flux status
flux get helmreleases -A | grep app-template

# Check for failed pods
kubectl get pods -A | grep -E 'Error|CrashLoopBackOff|ImagePullBackOff'

# Check resource usage
kubectl top pods -A --sort-by=memory | head -20
```

### Monitoring Points

#### Prometheus Metrics
Monitor these key metrics during and after upgrade:

1. **Pod Restart Count**
   ```promql
   increase(kube_pod_container_status_restarts_total[1h]) > 0
   ```

2. **Pod Status**
   ```promql
   kube_pod_status_phase{phase!="Running"} == 1
   ```

3. **HelmRelease Status**
   ```promql
   gotk_reconcile_condition{type="Ready",status="False"} == 1
   ```

4. **Resource Usage**
   ```promql
   container_memory_usage_bytes{namespace=~"media|home|utilities"}
   container_cpu_usage_seconds_total{namespace=~"media|home|utilities"}
   ```

#### Grafana Dashboards
Create or update dashboards to track:

1. **Upgrade Progress Dashboard**
   - HelmRelease versions
   - Pod status by namespace
   - Recent events
   - Resource usage trends

2. **Application Health Dashboard**
   - Service availability
   - Response times
   - Error rates
   - Resource consumption

#### Log Aggregation
Monitor logs for:

1. **Error Patterns**
   ```
   level=error
   level=fatal
   panic
   exception
   ```

2. **Upgrade Events**
   ```
   "helm upgrade"
   "chart version"
   "reconciliation"
   ```

3. **Application Errors**
   - Connection failures
   - Authentication errors
   - Database errors
   - File system errors

### Success Criteria

#### Per-Application Success
An application upgrade is considered successful when:

- [ ] HelmRelease status is Ready
- [ ] All pods are Running and Ready
- [ ] No error logs in last 10 minutes
- [ ] Ingress endpoint responds with 200 OK
- [ ] Core functionality verified
- [ ] Resource usage within normal range
- [ ] No alerts firing

#### Batch Success
A batch upgrade is considered successful when:

- [ ] All applications in batch meet per-application criteria
- [ ] No cluster-wide issues detected
- [ ] Flux reconciliation healthy
- [ ] No unexpected pod restarts
- [ ] Monitoring systems operational

#### Overall Success
The complete upgrade is considered successful when:

- [ ] All 32 releases upgraded to v4.3.0
- [ ] All applications operational
- [ ] No degraded services
- [ ] Monitoring and alerting functional
- [ ] Documentation updated
- [ ] Team trained on v4 changes

---

## Risk Mitigation

### Potential Issues

#### Issue 1: Pod Recreation Causes Downtime
**Probability:** High (expected behavior)  
**Impact:** Low to Medium  
**Affected:** All applications

**Symptoms:**
- Pods terminate and recreate
- Brief service interruption
- Ingress endpoints temporarily unavailable

**Mitigation:**
- **Prevention:**
  - Use rolling updates (default for Deployments)
  - Set appropriate `maxUnavailable` and `maxSurge`
  - Ensure readiness probes configured
  - Schedule during maintenance window

- **Detection:**
  - Monitor pod status during upgrade
  - Watch for prolonged termination
  - Check readiness probe failures

- **Resolution:**
  - Wait for rolling update to complete
  - Verify new pods reach Ready state
  - Check logs for startup errors
  - Rollback if pods fail to start

#### Issue 2: StatefulSet Ordered Recreation
**Probability:** High (expected behavior)  
**Impact:** Medium  
**Affected:** Stateful applications (plex, jellyfin, frigate, etc.)

**Symptoms:**
- Pods recreate one at a time
- Longer downtime than Deployments
- Data volume remounting

**Mitigation:**
- **Prevention:**
  - Schedule during low-usage periods
  - Notify users of expected downtime
  - Verify PVC health before upgrade
  - Ensure adequate storage space

- **Detection:**
  - Monitor StatefulSet rollout status
  - Watch for PVC mounting issues
  - Check for data corruption

- **Resolution:**
  - Allow StatefulSet to complete rollout
  - Verify data integrity after upgrade
  - Restore from backup if data issues
  - Rollback if persistent failures

#### Issue 3: Ingress Configuration Changes
**Probability:** Low  
**Impact:** Medium  
**Affected:** Applications with ingress

**Symptoms:**
- Ingress endpoints not accessible
- Certificate errors
- Routing failures

**Mitigation:**
- **Prevention:**
  - Verify ingress configuration before upgrade
  - Test ingress after each application
  - Keep DNS records updated
  - Monitor certificate expiration

- **Detection:**
  - Test ingress endpoints after upgrade
  - Check ingress controller logs
  - Verify TLS certificates
  - Monitor external DNS updates

- **Resolution:**
  - Verify ingress resource created correctly
  - Check ingress controller configuration
  - Manually update DNS if needed
  - Recreate ingress resource if corrupted

#### Issue 4: ServiceAccount Token Issues
**Probability:** Low  
**Impact:** High (if affected)  
**Affected:** Applications using ServiceAccount tokens

**Symptoms:**
- Authentication failures
- API access denied
- Application startup failures

**Mitigation:**
- **Prevention:**
  - Audit ServiceAccount usage before upgrade
  - Identify applications requiring tokens
  - Create projected volume tokens
  - Test token access

- **Detection:**
  - Monitor authentication errors
  - Check ServiceAccount configurations
  - Verify token mounts
  - Test API access

- **Resolution:**
  - Create ServiceAccount tokens manually
  - Update pod specs with token volumes
  - Use projected volume tokens (recommended)
  - Rollback if critical functionality broken

#### Issue 5: Label Selector Mismatches
**Probability:** Low  
**Impact:** Medium  
**Affected:** Monitoring, alerting, service discovery

**Symptoms:**
- Prometheus metrics missing
- Alerts not firing
- Service discovery failures
- Dashboard data gaps

**Mitigation:**
- **Prevention:**
  - Audit label selectors before upgrade
  - Update monitoring configurations
  - Test metric collection
  - Verify alert rules

- **Detection:**
  - Check Prometheus targets
  - Verify ServiceMonitor configurations
  - Test alert rules
  - Review dashboard queries

- **Resolution:**
  - Update label selectors to use new labels
  - Recreate ServiceMonitor resources
  - Update Prometheus rules
  - Modify Grafana dashboard queries

#### Issue 6: Resource Naming Conflicts
**Probability:** Very Low  
**Impact:** High  
**Affected:** Applications with external dependencies

**Symptoms:**
- Service name changes
- Endpoint updates
- DNS resolution failures
- Connection errors

**Mitigation:**
- **Prevention:**
  - Document external dependencies
  - Use stable service names
  - Avoid hardcoded endpoints
  - Test inter-service communication

- **Detection:**
  - Monitor service endpoints
  - Check DNS records
  - Test application connectivity
  - Review connection errors

- **Resolution:**
  - Update external configurations
  - Recreate services with stable names
  - Update DNS records
  - Rollback if critical dependencies broken

### Emergency Procedures

#### Emergency Rollback
If critical issues are discovered:

1. **Immediate Actions**
   ```bash
   # Suspend Flux reconciliation
   flux suspend kustomization apps
   
   # Identify affected applications
   kubectl get helmrelease -A | grep -v Ready
   
   # Check cluster health
   kubectl get nodes
   kubectl get pods -A | grep -v Running
   ```

2. **Rollback Process**
   ```bash
   # Revert git changes
   git log --oneline -10  # Find commit to revert
   git revert <commit-hash>
   git push
   
   # Resume Flux
   flux resume kustomization apps
   
   # Force reconciliation
   flux reconcile kustomization apps --with-source
   ```

3. **Validation**
   ```bash
   # Verify rollback
   kubectl get helmrelease -A | grep app-template
   
   # Check application health
   ./validate-app-template-upgrades.sh
   ```

#### Communication Plan
During emergency:

1. **Notify Stakeholders**
   - Post in team chat channel
   - Update status page
   - Email affected users
   - Document timeline

2. **Escalation Path**
   - Level 1: Primary operator
   - Level 2: Secondary operator + team lead
   - Level 3: Infrastructure team + management

3. **Post-Incident**
   - Conduct root cause analysis
   - Update documentation
   - Improve procedures
   - Schedule retry

---

## Appendix: Release Examples

### Example 1: Simple Stateless Application (imaginary)

**Current Configuration:**
```yaml
# kubernetes/apps/media/imaginary/app/helm-release.yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: imaginary
  namespace: media
spec:
  interval: 15m
  chart:
    spec:
      chart: app-template
      version: 3.1.0  # ← Change to 4.3.0
      sourceRef:
        kind: HelmRepository
        name: bjw-s
        namespace: flux-system
  values:
    controllers:
      main:
        containers:
          main:
            image:
              repository: nextcloud/aio-imaginary
              tag: latest
    service:
      main:
        controller: main  # ← Optional: can be removed
        ports:
          http:
            port: 9000
    ingress:
      main:
        enabled: true
        hosts:
          - host: imaginary.example.com
            paths:
              - path: /
                service:
                  identifier: main  # ← Optional: can be removed
                  port: http
```

**Changes Required:**
1. Update chart version: `3.1.0` → `4.3.0`
2. Optional: Remove redundant `controller: main` from service
3. Optional: Remove redundant `identifier: main` from ingress

**Risk Level:** LOW  
**Expected Downtime:** < 30 seconds (rolling update)

### Example 2: Stateful Application (frigate)

**Current Configuration:**
```yaml
# kubernetes/apps/home/frigate/app/helm-release.yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: frigate
  namespace: home
spec:
  chart:
    spec:
      chart: app-template
      version: 3.1.0  # ← Change to 4.3.0
  values:
    controllers:
      main:
        type: statefulset
        containers:
          main:
            image:
              repository: ghcr.io/blakeblackshear/frigate
              tag: 0.16.2
        statefulset:
          volumeClaimTemplates:
            - name: config
              accessMode: ReadWriteOnce
              size: 5Gi
              storageClass: longhorn
    service:
      main:
        controller: main  # ← Optional: can be removed
        ports:
          http:
            port: 5000
    persistence:
      media:
        type: nfs
        server: nas.example.com
        path: /volume2/nvr
```

**Changes Required:**
1. Update chart version: `3.1.0` → `4.3.0`
2. Optional: Remove redundant `controller: main` from service

**Risk Level:** MEDIUM  
**Expected Downtime:** 1-2 minutes (StatefulSet recreation)  
**Special Considerations:**
- Verify NFS mount after upgrade
- Check video recording continuity
- Test camera streams

### Example 3: Application with Multiple Controllers (mosquitto)

**Current Configuration:**
```yaml
# kubernetes/apps/home/mosquitto/app/helm-release.yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: mosquitto
spec:
  chart:
    spec:
      chart: app-template
      version: 3.7.3  # ← Change to 4.3.0
  values:
    controllers:
      mosquitto:
        containers:
          app:
            image:
              repository: eclipse-mosquitto
              tag: 2.0.22
    service:
      app:
        controller: mosquitto  # ← Keep (not redundant)
        type: LoadBalancer
        ports:
          http:
            port: 1883
```

**Changes Required:**
1. Update chart version: `3.7.3` → `4.3.0`
2. Keep `controller: mosquitto` (not redundant - controller name differs from service name)

**Risk Level:** HIGH (critical infrastructure)  
**Expected Downtime:** < 1 minute  
**Special Considerations:**
- MQTT broker for home automation
- Dependent services: frigate, esphome, home-assistant
- Monitor client reconnections
- Verify message delivery

### Example 4: Complex Application (magicmirror v2.6.0)

**Current Configuration:**
```yaml
# kubernetes/apps/home/magicmirror/app/helm-release.yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: magicmirror
  namespace: home
spec:
  chart:
    spec:
      chart: app-template
      version: 2.6.0  # ← Requires multi-step upgrade
  values:
    controllers:
      main:
        type: statefulset
        initContainers:
          install-modules:
            command: [/bin/sh, -c]
            args: ["apt update && apt install git nodejs npm -y && ..."]
            volumeMounts:
              - name: modules
                mountPath: /opt/magic_mirror/modules
        containers:
          main:
            image:
              repository: karsten13/magicmirror
              tag: v2.33.0
        statefulset:
          volumeClaimTemplates:
            - name: modules
              accessMode: ReadWriteOnce
              size: 1Gi
```

**Upgrade Path:**
1. **Step 1:** v2.6.0 → v3.1.0 (use v2→v3 upgrade script)
2. **Step 2:** v3.1.0 → v4.3.0 (standard upgrade)

**Risk Level:** HIGH  
**Expected Downtime:** 5-10 minutes  
**Special Considerations:**
- Complex init container with module installation
- Volume mounts must be preserved
- Test module functionality after upgrade
- Keep v2.6.0 backup for quick rollback

---

## Conclusion

This upgrade strategy provides a comprehensive, phased approach to migrating 32 helm releases from app-template v3.x to v4.3.0. The v3→v4 upgrade is significantly simpler than previous major version upgrades, with minimal breaking changes and strong backward compatibility.

### Key Takeaways

1. **Low Risk:** The upgrade is low-risk for most applications due to structural compatibility
2. **Phased Approach:** The phased rollout strategy minimizes impact and allows early issue detection
3. **Automation:** The provided scripts automate the upgrade process while maintaining safety
4. **Validation:** Comprehensive validation ensures application health at each step
5. **Rollback:** Clear rollback procedures provide safety net for unexpected issues

### Next Steps

1. **Review and Approve:** Team review of this strategy document
2. **Script Development:** Implement and test upgrade scripts
3. **Test Environment:** Validate upgrade process in test environment
4. **Production Execution:** Execute phased rollout in production
5. **Documentation:** Update operational documentation with v4 specifics

### Success Metrics

- All 32 releases upgraded to v4.3.0
- Zero data loss
- Minimal downtime (within SLA)
- No critical incidents
- Team confidence in v4 platform

---

**Document Status:** Ready for Review  
**Approval Required:** Infrastructure Team Lead  
**Implementation Target:** TBD based on team availability