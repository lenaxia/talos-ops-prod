#!/usr/bin/env python3
"""
Validate YAML files for duplicate anchors and other common YAML issues.
This script helps prevent Kubernetes manifest validation failures due to YAML syntax errors.
"""

import sys
import re
import argparse
from pathlib import Path

def find_duplicate_anchors(file_path):
    """Find duplicate YAML anchors in a file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Pattern to match YAML anchors (&name or &appname, etc.)
        anchor_pattern = r'&([a-zA-Z_][a-zA-Z0-9_-]*)\s+'
        
        # Find all anchors
        anchors = []
        for match in re.finditer(anchor_pattern, content):
            anchor_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            anchors.append({
                'name': anchor_name,
                'line': line_num,
                'full_match': match.group(0)
            })
        
        # Check for duplicates
        anchor_counts = {}
        for anchor in anchors:
            anchor_name = anchor['name']
            anchor_counts[anchor_name] = anchor_counts.get(anchor_name, 0) + 1
        
        # Find duplicate anchors
        duplicates = [a for a in anchors if anchor_counts[a['name']] > 1]
        
        return duplicates
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return []

def check_yaml_file(file_path):
    """Check a single YAML file for issues."""
    issues = []
    
    # Check for duplicate anchors
    duplicate_anchors = find_duplicate_anchors(file_path)
    if duplicate_anchors:
        for anchor in duplicate_anchors:
            issues.append({
                'type': 'duplicate_anchor',
                'file': file_path,
                'line': anchor['line'],
                'anchor': anchor['name'],
                'message': f"Duplicate YAML anchor '&{anchor['name']}' at line {anchor['line']}"
            })
    
    # Check for common YAML syntax issues
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for YAML tab/space mixing (YAML doesn't allow tabs)
        if '\t' in content:
            issues.append({
                'type': 'tabs_in_yaml',
                'file': file_path,
                'line': content[:content.find('\t')].count('\n') + 1,
                'message': 'YAML file contains tabs (use spaces only)'
            })
        
        # Check for malformed JSON expressions like ${TIMEZONE} without proper quotes
        if re.search(r'\$\{[^}]+\}', content) and 'env:' in content:
            # Find env blocks and check for unquoted template variables
            for match in re.finditer(r'(^\s+-\s+)([A-Z_]+):\s*\$\{[^}]+\}', content, re.MULTILINE):
                # Check if the value is properly quoted
                value_line = content[match.start():].count('\n') + 1
                issues.append({
                    'type': 'unquoted_template_variable',
                    'file': file_path,
                    'line': value_line,
                    'message': f"Unquoted template variable in YAML at line {value_line}"
                })
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
    
    return issues

def validate_yaml_files(directories, extensions=None):
    """Validate all YAML files in given directories."""
    if extensions is None:
        extensions = ['.yaml', '.yml']
    
    all_issues = []
    files_checked = 0
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue
        
        for ext in extensions:
            for file_path in dir_path.rglob(f'**/*{ext}'):
                # Skip template files (.yaml.j2)
                if file_path.suffix == '.j2':
                    continue
                
                files_checked += 1
                issues.extend(check_yaml_file(file_path))
    
    return all_issues, files_checked

def main():
    parser = argparse.ArgumentParser(description='Validate YAML files for common issues')
    parser.add_argument('directories', nargs='+', help='Directories to validate')
    parser.add_argument('--extensions', nargs='+', default=['.yaml', '.yml'], help='YAML file extensions to check')
    parser.add_argument('--exit-code', type=int, default=1, help='Exit code on errors')
    
    args = parser.parse_args()
    
    issues, files_checked = files_checked(args.directories, args.extensions)
    
    # Sort issues by file and line
    issues.sort(key=lambda x: (x['file'], x['line']))
    
    # Group issues by type
    duplicate_anchor_issues = [i for i in issues if i['type'] == 'duplicate_anchor']
    other_issues = [i for i in issues if i['type'] != 'duplicate_anchor']
    
    # Report findings
    print(f"Validated {files_checked} YAML files")
    
    if duplicate_anchor_issues:
        print(f"\n❌ Found {len(duplicate_anchor_issues)} files with duplicate YAML anchors:")
        for issue in duplicate_anchor_issues:
            print(f"  - {issue['file']}:{issue['line']} - {issue['message']}")
    
    if other_issues:
        print(f"\n⚠️  Found {len(other_issues)} other YAML issues:")
        for issue in other_issues:
            print(f"  - {issue['file']}:{issue['line']} - {issue['message']}")
    
    if issues:
        print(f"\n❌ YAML validation failed with {len(issues)} issue(s)")
        sys.exit(args.exit_code)
    else:
        print(f"✅ All YAML files are valid")
        sys.exit(0)

if __name__ == '__main__':
    main()
