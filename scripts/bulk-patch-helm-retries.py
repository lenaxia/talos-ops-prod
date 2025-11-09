#!/usr/bin/env python3
"""
Bulk patch spec.upgrade.remediation.retries in HelmRelease files
"""

import argparse
import sys
from pathlib import Path
from ruamel.yaml import YAML

def patch_helm_retries(file_path: Path, retry_value: int, dry_run: bool = False) -> tuple[bool, str, str]:
    """
    Patch a single HelmRelease file
    Returns: (success, old_value, message)
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    
    try:
        with open(file_path, 'r') as f:
            data = yaml.load(f)
        
        # Check if spec.upgrade exists
        if 'spec' not in data or 'upgrade' not in data['spec']:
            return False, 'N/A', 'No spec.upgrade section'
        
        # Get current value
        if 'remediation' not in data['spec']['upgrade']:
            data['spec']['upgrade']['remediation'] = {}
        
        current = data['spec']['upgrade']['remediation'].get('retries', 'null')
        
        # Check if already set
        if current == retry_value:
            return False, str(current), f'Already {retry_value}'
        
        # Update value
        data['spec']['upgrade']['remediation']['retries'] = retry_value
        
        # Write back
        if not dry_run:
            with open(file_path, 'w') as f:
                yaml.dump(data, f)
        
        return True, str(current), f'{current} → {retry_value}'
        
    except Exception as e:
        return False, 'error', f'Error: {str(e)}'

def main():
    parser = argparse.ArgumentParser(description='Bulk patch HelmRelease retry values')
    parser.add_argument('--retries', type=int, default=3, help='Retry value to set (default: 3)')
    parser.add_argument('--dir', default='kubernetes/apps', help='Target directory (default: kubernetes/apps)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without modifying files')
    parser.add_argument('--pattern', default='**/helm-release.yaml', help='File pattern to match')
    
    args = parser.parse_args()
    
    print(f"=== Bulk Patching HelmRelease Retry Values ===")
    print(f"Target directory: {args.dir}")
    print(f"Retry value: {args.retries}")
    print(f"Dry run: {args.dry_run}")
    print()
    
    target_dir = Path(args.dir)
    if not target_dir.exists():
        print(f"Error: Directory {target_dir} does not exist")
        sys.exit(1)
    
    # Find all matching files
    files = list(target_dir.glob(args.pattern))
    files.extend(target_dir.glob('**/helmrelease.yaml'))
    files = sorted(set(files))
    
    updated = 0
    skipped = 0
    errors = 0
    
    for file_path in files:
        success, old_value, message = patch_helm_retries(file_path, args.retries, args.dry_run)
        
        try:
            rel_path = file_path.relative_to(Path.cwd())
        except ValueError:
            rel_path = file_path
        
        if success:
            print(f"✓ {rel_path}: {message}")
            updated += 1
        else:
            if 'Error' in message:
                print(f"✗ {rel_path}: {message}")
                errors += 1
            else:
                print(f"⊘ {rel_path}: {message}")
                skipped += 1
    
    print()
    print("=== Summary ===")
    print(f"Total files: {len(files)}")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")
    
    if updated > 0 and not args.dry_run:
        print()
        print(f"Review changes: git diff {args.dir}")
        print(f"Commit: git add {args.dir} && git commit -m 'chore: update helm retry values to {args.retries}'")
    elif updated > 0 and args.dry_run:
        print()
        print("Run without --dry-run to apply changes")

if __name__ == '__main__':
    main()