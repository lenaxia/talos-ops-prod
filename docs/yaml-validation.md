# YAML Validation

This repository includes automated YAML validation tools to prevent indentation and syntax errors.

## Validation Script

### validate-yaml-indentation.py

This script checks for:
- YAML syntax errors
- Incorrect indentation (service/ingress key nesting issues)
- Duplicate keys at the same indentation level

### Usage

Check a single file:
```bash
python scripts/validate-yaml-indentation.py kubernetes/apps/media/nzbhydra2/app/helm-release.yaml
```

Check multiple files:
```bash
python scripts/validate-yaml-indentation.py kubernetes/apps/media/*/app/helm-release.yaml
```

Check all YAML files in a directory:
```bash
find kubernetes -name "*.yaml" -exec python scripts/validate-yaml-indentation.py {} +
```

## Pre-commit Hook

The repository includes a pre-commit configuration (`.pre-commit-config.yaml`) that automatically runs YAML validation before each commit.

### Installation

1. Install pre-commit:
```bash
pip install pre-commit
```

2. Install the hooks:
```bash
pre-commit install
```

Now the YAML validation will run automatically before each commit.

### Running Manually

To run all pre-commit hooks manually:
```bash
pre-commit run --all-files
```

## Common Issues

### Service/Ingress Indentation

Incorrect:
```yaml
service:
main:              # ❌ Wrong indentation
  type: ClusterIP
```

Correct:
```yaml
service:
  main:            # ✓ Properly nested
    type: ClusterIP
```

### Duplicate Keys

Incorrect:
```yaml
controllers:
  main:
    type: statefulset
  main:            # ❌ Duplicate key
    type: deployment
```

Correct:
```yaml
controllers:
  main:
    type: statefulset
  secondary:       # ✓ Unique key
    type: deployment
```

## CI/CD Integration

The `task kubernetes:kubeconform` command validates all Kubernetes manifests during CI/CD. The validation scripts help catch issues earlier in the development process.
