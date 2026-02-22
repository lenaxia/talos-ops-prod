#!/usr/bin/env python3
"""
Validate HelmRelease manifests for common configuration errors.

This script checks HelmRelease files for:
1. Invalid upgrade.strategy field (should be under remediation, not directly under upgrade)
2. Other common schema violations
"""

import sys
import yaml
from pathlib import Path
from typing import List, Dict, Any

def check_helmrelease(filepath: Path) -> List[str]:
    """
    Check a HelmRelease file for configuration errors.
    
    Returns a list of error messages.
    """
    errors = []
    
    try:
        with open(filepath, 'r') as f:
            content = yaml.safe_load(f)
    except Exception as e:
        return [f"Failed to parse YAML: {e}"]
    
    if not isinstance(content, dict):
        return ["File does not contain a valid YAML document"]
    
    # Check if it's a HelmRelease
    if content.get('kind') != 'HelmRelease':
        return []
    
    if content.get('apiVersion') != 'helm.toolkit.fluxcd.io/v2':
        return []
    
    spec = content.get('spec', {})
    upgrade = spec.get('upgrade', {})
    
    # Check for upgrade.strategy field (invalid - should be under remediation)
    if 'strategy' in upgrade:
        errors.append(
            f"Invalid 'upgrade.strategy' field found. "
            f"In HelmRelease v2, 'strategy' should be under 'upgrade.remediation', "
            f"not directly under 'upgrade'. Please remove 'upgrade.strategy' or "
            f"move it to 'upgrade.remediation.strategy'."
        )
    
    # Check that remediation strategy is valid (if present)
    remediation = upgrade.get('remediation', {})
    if 'strategy' in remediation:
        strategy = remediation['strategy']
        valid_strategies = ['rollback', 'uninstall']
        if strategy not in valid_strategies:
            errors.append(
                f"Invalid remediation strategy '{strategy}'. "
                f"Valid values are: {', '.join(valid_strategies)}"
            )
    
    return errors


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: validate-helmrelease.py <path>")
        sys.exit(1)
    
    path = Path(sys.argv[1])
    
    all_errors = []
    
    if path.is_file():
        errors = check_helmrelease(path)
        if errors:
            all_errors.extend([f"{path}: {e}" for e in errors])
    elif path.is_dir():
        # Find all YAML files in the directory
        for yaml_file in path.rglob('*.yaml'):
            if 'helm-release' in yaml_file.name or 'helmrelease' in yaml_file.name:
                errors = check_helmrelease(yaml_file)
                if errors:
                    all_errors.extend([f"{yaml_file}: {e}" for e in errors])
    
    if all_errors:
        print("HelmRelease validation failed:")
        for error in all_errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("HelmRelease validation passed.")
        sys.exit(0)


if __name__ == '__main__':
    main()
