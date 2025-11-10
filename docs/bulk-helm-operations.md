# Bulk HelmRelease Operations

This document describes tools and procedures for performing bulk operations on HelmRelease resources across the cluster.

## Overview

The bulk patch scripts allow you to modify configuration values across multiple HelmRelease files without editing them individually. This is useful for:

- Standardizing retry values across all releases
- Applying configuration changes to multiple applications
- Maintaining consistency across the cluster

## Available Scripts

### 1. Bash Script: `bulk-patch-helm-retries.sh`

A simple bash script using `yq` for quick operations.

**Location:** [`scripts/bulk-patch-helm-retries.sh`](../scripts/bulk-patch-helm-retries.sh)

**Requirements:**
- `yq` (YAML processor)
- `bash`
- `find`

**Usage:**
```bash
./scripts/bulk-patch-helm-retries.sh [RETRY_VALUE] [TARGET_DIR]
```

**Parameters:**
- `RETRY_VALUE`: Number of retries to set (default: 3)
- `TARGET_DIR`: Directory to search (default: kubernetes/apps)

**Examples:**
```bash
# Set all retries to 3 (default)
./scripts/bulk-patch-helm-retries.sh

# Set all retries to 5
./scripts/bulk-patch-helm-retries.sh 5

# Set retries to 5 in media apps only
./scripts/bulk-patch-helm-retries.sh 5 kubernetes/apps/media

# Set retries to 10 in databases
./scripts/bulk-patch-helm-retries.sh 10 kubernetes/apps/databases
```

### 2. Python Script: `bulk-patch-helm-retries.py`

A more feature-rich Python script with dry-run support and better error handling.

**Location:** [`scripts/bulk-patch-helm-retries.py`](../scripts/bulk-patch-helm-retries.py)

**Requirements:**
- Python 3.10+
- `ruamel.yaml` package (install via: `pip install ruamel.yaml`)

**Usage:**
```bash
./scripts/bulk-patch-helm-retries.py [OPTIONS]
```

**Options:**
- `--retries N`: Retry value to set (default: 3)
- `--dir PATH`: Target directory (default: kubernetes/apps)
- `--dry-run`: Show changes without applying them
- `--pattern GLOB`: File pattern to match (default: **/helm-release.yaml)

**Examples:**
```bash
# Dry-run: see what would change
./scripts/bulk-patch-helm-retries.py --retries 5 --dry-run

# Apply changes to all apps
./scripts/bulk-patch-helm-retries.py --retries 5

# Target specific directory
./scripts/bulk-patch-helm-retries.py --retries 3 --dir kubernetes/apps/media

# Custom file pattern
./scripts/bulk-patch-helm-retries.py --retries 5 --pattern "**/helmrelease.yaml"
```

## What Gets Modified

Both scripts modify the following field in HelmRelease files:

```yaml
spec:
  upgrade:
    remediation:
      retries: <VALUE>
```

## Safety Features

### Pre-flight Checks
- Scripts verify files have `spec.upgrade` section before attempting changes
- Files already at target value are skipped
- Invalid files are reported but don't stop the process

### Dry-run Mode (Python only)
Always test changes first:
```bash
./scripts/bulk-patch-helm-retries.py --retries 5 --dry-run
```

### Git Integration
Both scripts provide git commands for review and commit:
```bash
# Review changes
git diff kubernetes/apps

# Commit changes
git add kubernetes/apps
git commit -m 'chore: update helm retry values to 5'
```

## Workflow

### Recommended Process

1. **Dry-run first** (Python script):
   ```bash
   ./scripts/bulk-patch-helm-retries.py --retries 5 --dry-run
   ```

2. **Review the output** to understand what will change

3. **Apply changes**:
   ```bash
   ./scripts/bulk-patch-helm-retries.py --retries 5
   ```

4. **Review git diff**:
   ```bash
   git diff kubernetes/apps
   ```

5. **Test on a subset** if concerned:
   ```bash
   ./scripts/bulk-patch-helm-retries.py --retries 5 --dir kubernetes/apps/media
   ```

6. **Commit changes**:
   ```bash
   git add kubernetes/apps
   git commit -m 'chore: update helm retry values to 5'
   ```

7. **Push and monitor**:
   ```bash
   git push
   flux reconcile kustomization --with-source flux-system
   ```

## Rollback Procedures

### If Changes Haven't Been Committed

```bash
# Discard all changes
git restore kubernetes/apps

# Discard specific directory
git restore kubernetes/apps/media
```

### If Changes Have Been Committed

```bash
# Revert the commit
git revert HEAD

# Or reset to previous commit (if not pushed)
git reset --hard HEAD~1
```

### If Changes Have Been Pushed

```bash
# Revert and push
git revert HEAD
git push

# Force Flux to reconcile
flux reconcile kustomization --with-source flux-system
```

## Common Scenarios

### Scenario 1: Increase Retries for Flaky Apps

Problem: Some apps fail to upgrade due to transient issues.

Solution:
```bash
# Increase retries to 5 for all apps
./scripts/bulk-patch-helm-retries.py --retries 5
```

### Scenario 2: Standardize Configuration

Problem: Different apps have different retry values.

Solution:
```bash
# Standardize all to 3 retries
./scripts/bulk-patch-helm-retries.sh 3
```

### Scenario 3: Target Specific Category

Problem: Media apps need more retries than others.

Solution:
```bash
# Set media apps to 10 retries
./scripts/bulk-patch-helm-retries.py --retries 10 --dir kubernetes/apps/media

# Keep others at 3
./scripts/bulk-patch-helm-retries.py --retries 3 --dir kubernetes/apps/databases
```

### Scenario 4: Test Before Applying

Problem: Want to see impact before making changes.

Solution:
```bash
# Dry-run to see what would change
./scripts/bulk-patch-helm-retries.py --retries 5 --dry-run | tee /tmp/changes.txt

# Review the output
less /tmp/changes.txt

# Apply if satisfied
./scripts/bulk-patch-helm-retries.py --retries 5
```

## Troubleshooting

### Script Reports "No spec.upgrade section"

This is normal for HelmReleases that don't have upgrade configuration. These are skipped automatically.

### Permission Denied

Make scripts executable:
```bash
chmod +x scripts/bulk-patch-helm-retries.sh
chmod +x scripts/bulk-patch-helm-retries.py
```

### Python Script Fails with Import Error

Install required package:
```bash
pip install ruamel.yaml

# Or if using venv
./venv/bin/pip install ruamel.yaml
```

### yq Command Not Found

Install yq:
```bash
# On Ubuntu/Debian
sudo apt-get install yq

# On macOS
brew install yq

# Or download binary from https://github.com/mikefarah/yq
```

### Changes Not Applied

Check file permissions and ensure you're running from the repository root:
```bash
cd /home/mikekao/personal/talos-ops-prod
./scripts/bulk-patch-helm-retries.py --retries 5
```

## Best Practices

1. **Always dry-run first** when using the Python script
2. **Test on a small subset** before applying to all apps
3. **Review git diff** before committing
4. **Commit with descriptive messages** that include the retry value
5. **Monitor Flux reconciliation** after pushing changes
6. **Keep retry values reasonable** (3-10 is typical)
7. **Document why** you're changing values in commit messages
8. **Backup before bulk operations** if making experimental changes

## Related Documentation

- [Flux HelmRelease Specification](https://fluxcd.io/flux/components/helm/helmreleases/)
- [App Template v4 Upgrade Guide](./app-template-v4-quick-reference.md)
- [Helm Upgrade Remediation](https://fluxcd.io/flux/components/helm/helmreleases/#configuring-failure-remediation)

## Script Output Examples

### Bash Script Output
```
=== Bulk Patching HelmRelease Retry Values ===
Target directory: kubernetes/apps
Retry value: 5

✓ Updated kubernetes/apps/media/plex/app/helm-release.yaml (3 → 5)
✓ kubernetes/apps/media/sonarr/app/helm-release.yaml (already 5)
⊘ Skipping kubernetes/apps/kube-system/cilium/app/helmrelease.yaml (no spec.upgrade section)

=== Summary ===
Total files found: 45
Updated: 23
Skipped: 22

Review changes with: git diff kubernetes/apps
Commit with: git add kubernetes/apps && git commit -m 'chore: update helm retry values to 5'
```

### Python Script Output (Dry-run)
```
=== Bulk Patching HelmRelease Retry Values ===
Target directory: kubernetes/apps
Retry value: 5
Dry run: True

✓ kubernetes/apps/media/plex/app/helm-release.yaml: 3 → 5
⊘ kubernetes/apps/media/sonarr/app/helm-release.yaml: Already 5
⊘ kubernetes/apps/kube-system/cilium/app/helmrelease.yaml: No spec.upgrade section

=== Summary ===
Total files: 45
Updated: 23
Skipped: 22
Errors: 0

Run without --dry-run to apply changes