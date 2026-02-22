# Pre-commit Hooks

This repository uses pre-commit hooks to validate changes before they are committed.

## Installation

```bash
pip install pre-commit
pre-commit install
```

## Available Hooks

### validate-helmrelease-upgrade

Validates HelmRelease `upgrade.strategy` configuration to ensure it conforms to the expected schema:

- **Error**: `strategy: <string>` directly under `upgrade:`
- **Expected**: Either:
  - `upgrade.remediation.strategy: <string>` (for remediation strategy)
  - `upgrade.strategy.type: <string>` (for top-level upgrade strategy)

This prevents the common issue where HelmRelease manifests fail schema validation with:
```
jsonschema validation failed - at '/spec/upgrade/strategy': got string, want object
```
