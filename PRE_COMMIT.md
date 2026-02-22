# Pre-commit Hooks

This repository uses pre-commit hooks to validate changes before they are committed.

## Installation

1. Install pre-commit:
   ```bash
   pip install pre-commit
   ```

2. Install the hooks:
   ```bash
   pre-commit install
   ```

## Available Hooks

### validate-helmrelease-upgrade

Validates that `upgrade.strategy` in HelmRelease files is correctly configured. This hook ensures that the `strategy` field is properly placed under `upgrade.remediation.strategy` rather than directly under `upgrade`.

**Trigger:** Any change to `helm-release.yaml` files in the `kubernetes/apps/` directory

## Running Hooks Manually

To run all hooks manually:
```bash
pre-commit run --all-files
```

To run a specific hook:
```bash
pre-commit run validate-helmrelease-upgrade --all-files
```

## Troubleshooting

If a hook fails:
1. Read the error message carefully - it will indicate which file has the issue and what needs to be fixed
2. Make the necessary corrections
3. Run the hook again to verify the fix

## Skipping Hooks (Not Recommended)

To bypass hooks temporarily (use with caution):
```bash
git commit --no-verify
```

**Note:** Skipping hooks may allow invalid configurations to be committed, which can cause CI failures or runtime errors.
