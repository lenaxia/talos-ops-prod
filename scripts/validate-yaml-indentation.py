#!/usr/bin/env python3
"""
YAML indentation validation script.
Checks for common indentation issues in HelmRelease and values files.
"""

import yaml
import sys
import re
from pathlib import Path

def validate_yaml_syntax(filepath):
    """Validate YAML syntax."""
    try:
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        return True, None
    except yaml.YAMLError as e:
        return False, str(e)

def check_indentation_issues(filepath):
    """
    Check for common indentation issues.
    
    Specifically looks for:
    - service: followed by incorrectly indented keys
    - ingress: followed by incorrectly indented keys
    - Multiple keys at same level that should be nested
    """
    issues = []
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Check for service/ingress indentation issues
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        
        # Skip comments and empty lines
        if not stripped or stripped.startswith('#'):
            continue
            
        # Check for service: or ingress: keys
        if stripped in ['service:', 'ingress:', 'controllers:']:
            # Get the indentation of this line
            indent = len(line) - len(line.lstrip())
            
            # Check next non-empty, non-comment lines for proper indentation
            for j in range(i, min(i + 20, len(lines))):
                next_line = lines[j].rstrip()
                if next_line and not next_line.strip().startswith('#'):
                    next_indent = len(next_line) - len(next_line.lstrip())
                    
                    # Next key should be indented more than current key
                    if next_indent <= indent:
                        issues.append(
                            f"Line {j+1}: Key after '{stripped}' has incorrect indentation "
                            f"(expected > {indent} spaces, got {next_indent})"
                        )
                    
                    # Also check if the next key is at the same level as service/ingress
                    # but should be nested
                    if stripped in ['service:', 'ingress:'] and next_indent == indent:
                        issues.append(
                            f"Line {j+1}: Key should be nested under '{stripped}', "
                            f"not at the same level"
                        )
                    
                    break
    
    # Check for duplicate keys at same indentation level
    key_indents = {}
    current_indent = 0
    
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        
        if not stripped or stripped.startswith('#'):
            continue
            
        # Calculate indentation
        indent = len(line) - len(line.lstrip())
        
        # Check if this is a key (ends with colon)
        if stripped.endswith(':'):
            # Track keys at this indentation level
            if indent not in key_indents:
                key_indents[indent] = {}
            
            # Extract the key name
            key_name = stripped[:-1]
            
            # Check for duplicate keys at same level
            if key_name in key_indents[indent]:
                prev_line = key_indents[indent][key_name]
                issues.append(
                    f"Line {i}: Duplicate key '{key_name}' "
                    f"(previously defined at line {prev_line})"
                )
            else:
                key_indents[indent][key_name] = i
    
    return issues

def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python validate-yaml-indentation.py <file1> [file2] ...")
        print("\nOr use with find to check all YAML files:")
        print('  find kubernetes -name "*.yaml" -exec python validate-yaml-indentation.py {} +')
        sys.exit(1)
    
    all_issues = []
    
    for filepath in sys.argv[1:]:
        filepath = Path(filepath)
        
        if not filepath.exists():
            print(f"⚠️  File not found: {filepath}")
            continue
        
        print(f"\nChecking {filepath}...")
        
        # Validate YAML syntax
        is_valid, error = validate_yaml_syntax(filepath)
        if not is_valid:
            print(f"  ❌ YAML syntax error: {error}")
            all_issues.append((str(filepath), "SYNTAX_ERROR", error))
            continue
        
        # Check for indentation issues
        issues = check_indentation_issues(filepath)
        if issues:
            print(f"  ⚠️  Found {len(issues)} indentation issue(s):")
            for issue in issues:
                print(f"    - {issue}")
                all_issues.append((str(filepath), "INDENTATION", issue))
        else:
            print(f"  ✓ No issues found")
    
    # Summary
    print("\n" + "="*60)
    if all_issues:
        print(f"❌ Found {len(all_issues)} issue(s) across {len(sys.argv)-1} file(s)")
        sys.exit(1)
    else:
        print(f"✓ All files are valid!")
        sys.exit(0)

if __name__ == '__main__':
    main()
