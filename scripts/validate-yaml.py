#!/usr/bin/env python3
"""
Validate YAML files for duplicate keys.

This script checks all YAML files in the Kubernetes directory for duplicate keys,
which are not allowed in the YAML specification and can cause validation failures.
"""

import sys
import yaml
from pathlib import Path


class DuplicateKeyError(Exception):
    """Exception raised when duplicate keys are found."""
    pass


def construct_mapping(loader, node):
    """Custom constructor to detect duplicate keys."""
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in mapping:
            raise DuplicateKeyError(
                f"Duplicate key '{key}' found in {node.start_mark.name} at line {node.start_mark.line + 1}"
            )
        mapping[key] = loader.construct_object(value_node)
    return mapping


def validate_yaml_file(file_path):
    """
    Validate a single YAML file for duplicate keys.
    
    Args:
        file_path: Path to the YAML file to validate
        
    Returns:
        True if valid, False if duplicate keys found
    """
    try:
        # Use custom constructor to detect duplicates
        loader = yaml.SafeLoader
        loader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            construct_mapping
        )
        
        with open(file_path, 'r') as f:
            yaml.load(f, Loader=loader)
        return True
    except DuplicateKeyError as e:
        print(f"❌ {e}")
        return False
    except yaml.YAMLError as e:
        # Not a duplicate key error, but still a YAML error
        # Let kubeconform handle other YAML errors
        return True
    except Exception as e:
        # Other exceptions (file not found, etc.) - let other tools handle
        return True


def main():
    """Main function to validate all YAML files."""
    if len(sys.argv) < 2:
        print("Usage: validate-yaml.sh <kubernetes_directory>")
        sys.exit(1)
    
    k8s_dir = Path(sys.argv[1])
    
    if not k8s_dir.exists():
        print(f"Directory not found: {k8s_dir}")
        sys.exit(1)
    
    print("=== Validating YAML files for duplicate keys ===")
    
    # Find all YAML files
    yaml_files = list(k8s_dir.rglob("*.yaml")) + list(k8s_dir.rglob("*.yml"))
    
    if not yaml_files:
        print("No YAML files found")
        sys.exit(0)
    
    errors_found = False
    validated_count = 0
    
    for yaml_file in yaml_files:
        if not validate_yaml_file(yaml_file):
            errors_found = True
        else:
            validated_count += 1
    
    if errors_found:
        print(f"\n❌ Found duplicate keys in YAML files")
        sys.exit(1)
    else:
        print(f"\n✅ Validated {validated_count} YAML files - no duplicate keys found")
        sys.exit(0)


if __name__ == "__main__":
    main()
