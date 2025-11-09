#!/usr/bin/env python3
"""
App-Template v4 Upgrade Script

This script automates the upgrade of bjw-s app-template Helm releases from v3.x to v4.3.0.

The v3→v4 upgrade is simpler than previous major version upgrades because:
- The YAML structure remains largely compatible
- Most changes are handled automatically by the chart
- Only the chart version number needs updating in most cases
- Optional optimizations can remove redundant fields

Usage:
    python hack/app-template-upgrade-v4.py [OPTIONS] FILE [FILE ...]
    python hack/app-template-upgrade-v4.py [OPTIONS] kubernetes/apps/media/*/app/helm-release.yaml

Options:
    --dry-run       Preview changes without writing files
    --verbose       Enable detailed logging
    --optimize      Apply optional optimizations (remove redundant fields)
    --help          Show this help message

Examples:
    # Single file with dry-run
    python hack/app-template-upgrade-v4.py --dry-run kubernetes/apps/media/bazarr/app/helm-release.yaml

    # Multiple files with optimizations
    python hack/app-template-upgrade-v4.py --optimize kubernetes/apps/media/*/app/helm-release.yaml

    # Verbose mode for debugging
    python hack/app-template-upgrade-v4.py --verbose --dry-run kubernetes/apps/home/frigate/app/helm-release.yaml
"""

import argparse
import glob
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ruamel.yaml import YAML

LOG = logging.getLogger('app-template-upgrade-v4')

TARGET_VERSION = '4.3.0'
HELM_RELEASE_NAMES = ['helmrelease.yaml', 'helm-release.yaml']


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    LOG.setLevel(level)
    
    if not LOG.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        handler.setFormatter(formatter)
        LOG.addHandler(handler)


def load_yaml_file(filepath: Path) -> Any:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    
    with open(filepath, 'r') as file:
        return yaml.load(file)


def save_yaml_file(filepath: Path, data: Any) -> None:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    
    with open(filepath, 'w') as file:
        yaml.dump(data, file)


def get_nested_value(data: Dict, path: str) -> Optional[Any]:
    value = data
    for key in path.split('.'):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def is_app_template_release(data: Dict) -> bool:
    return (
        data.get('kind') == 'HelmRelease' and
        get_nested_value(data, 'spec.chart.spec.chart') == 'app-template'
    )


def get_current_version(data: Dict) -> Optional[str]:
    return get_nested_value(data, 'spec.chart.spec.version')


def should_process_file(filepath: Path, data: Dict) -> Tuple[bool, str]:
    if not is_app_template_release(data):
        return False, "Not an app-template HelmRelease"
    
    current_version = get_current_version(data)
    if not current_version:
        return False, "Could not determine current version"
    
    if current_version.startswith('2.'):
        return False, f"Version {current_version} requires v2→v3 upgrade first (use app-template-upgrade-v3.py)"
    
    if current_version.startswith('4.'):
        return False, f"Already on v4.x ({current_version})"
    
    if not current_version.startswith('3.'):
        return False, f"Unexpected version: {current_version}"
    
    return True, f"Ready to upgrade from {current_version} to {TARGET_VERSION}"


def count_controllers(data: Dict) -> int:
    controllers = get_nested_value(data, 'spec.values.controllers')
    if not controllers or not isinstance(controllers, dict):
        return 0
    return len(controllers)


def count_services(data: Dict) -> int:
    services = get_nested_value(data, 'spec.values.service')
    if not services or not isinstance(services, dict):
        return 0
    return len(services)


def optimize_services(data: Dict) -> List[str]:
    changes = []
    services = get_nested_value(data, 'spec.values.service')
    
    if not services or not isinstance(services, dict):
        return changes
    
    controller_count = count_controllers(data)
    
    if controller_count == 1:
        for service_name, service_config in services.items():
            if isinstance(service_config, dict) and 'controller' in service_config:
                controller_value = service_config['controller']
                del service_config['controller']
                changes.append(
                    f"  - Removed redundant 'controller: {controller_value}' from service '{service_name}'"
                )
    
    return changes


def optimize_ingress(data: Dict) -> List[str]:
    changes = []
    ingress = get_nested_value(data, 'spec.values.ingress')
    
    if not ingress or not isinstance(ingress, dict):
        return changes
    
    service_count = count_services(data)
    
    if service_count == 1:
        for ingress_name, ingress_config in ingress.items():
            if not isinstance(ingress_config, dict):
                continue
            
            hosts = ingress_config.get('hosts', [])
            for host in hosts:
                if not isinstance(host, dict):
                    continue
                
                paths = host.get('paths', [])
                for path in paths:
                    if not isinstance(path, dict):
                        continue
                    
                    service = path.get('service')
                    if isinstance(service, dict) and 'identifier' in service:
                        identifier_value = service['identifier']
                        del service['identifier']
                        changes.append(
                            f"  - Removed redundant 'service.identifier: {identifier_value}' from ingress '{ingress_name}'"
                        )
    
    return changes


def upgrade_file(filepath: Path, dry_run: bool = False, optimize: bool = False) -> Tuple[bool, List[str]]:
    changes = []
    
    try:
        data = load_yaml_file(filepath)
    except Exception as exc:
        LOG.error(f"Failed to load {filepath}: {exc}")
        return False, []
    
    should_process, reason = should_process_file(filepath, data)
    if not should_process:
        LOG.debug(f"Skipping {filepath}: {reason}")
        return False, [reason]
    
    current_version = get_current_version(data)
    
    data['spec']['chart']['spec']['version'] = TARGET_VERSION
    changes.append(f"Updated chart version: {current_version} → {TARGET_VERSION}")
    
    if optimize:
        service_changes = optimize_services(data)
        changes.extend(service_changes)
        
        ingress_changes = optimize_ingress(data)
        changes.extend(ingress_changes)
    
    if not dry_run:
        try:
            save_yaml_file(filepath, data)
            LOG.info(f"✓ Updated {filepath}")
        except Exception as exc:
            LOG.error(f"Failed to save {filepath}: {exc}")
            return False, changes
    else:
        LOG.info(f"[DRY-RUN] Would update {filepath}")
    
    return True, changes


def process_files(
    file_patterns: List[str],
    dry_run: bool = False,
    verbose: bool = False,
    optimize: bool = False
) -> Tuple[int, int, int]:
    setup_logging(verbose)
    
    all_files = []
    for pattern in file_patterns:
        expanded = glob.glob(pattern, recursive=True)
        if not expanded:
            path = Path(pattern)
            if path.exists() and path.is_file():
                all_files.append(str(path))
        else:
            all_files.extend(expanded)
    
    if not all_files:
        LOG.error("No files found matching the provided patterns")
        return 0, 0, 0
    
    LOG.info(f"Found {len(all_files)} file(s) to process")
    if dry_run:
        LOG.info("Running in DRY-RUN mode - no files will be modified")
    if optimize:
        LOG.info("Optimization mode enabled - will remove redundant fields")
    LOG.info("")
    
    processed = 0
    skipped = 0
    failed = 0
    
    for filepath_str in all_files:
        filepath = Path(filepath_str)
        
        if filepath.name not in HELM_RELEASE_NAMES:
            LOG.debug(f"Skipping {filepath}: not a helm-release file")
            skipped += 1
            continue
        
        success, changes = upgrade_file(filepath, dry_run, optimize)
        
        if success:
            processed += 1
            if changes:
                for change in changes:
                    LOG.info(f"  {change}")
                LOG.info("")
        elif changes:
            skipped += 1
            if verbose:
                LOG.debug(f"  {changes[0]}")
        else:
            failed += 1
    
    return processed, skipped, failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Upgrade bjw-s app-template Helm releases from v3.x to v4.3.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single file with dry-run
  %(prog)s --dry-run kubernetes/apps/media/bazarr/app/helm-release.yaml

  # Multiple files with optimizations
  %(prog)s --optimize kubernetes/apps/media/*/app/helm-release.yaml

  # Verbose mode for debugging
  %(prog)s --verbose --dry-run kubernetes/apps/home/frigate/app/helm-release.yaml

Special Cases:
  - Files on v2.x will be skipped with a warning to run app-template-upgrade-v3.py first
  - Files already on v4.x will be skipped
  - Only app-template HelmRelease files will be processed

Optimizations (--optimize flag):
  - Removes redundant 'controller' field from services when only one controller exists
  - Removes redundant 'service.identifier' from ingress paths when only one service exists
        """
    )
    
    parser.add_argument(
        'files',
        nargs='+',
        help='Helm release file(s) or glob pattern(s) to process'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable detailed logging output'
    )
    
    parser.add_argument(
        '--optimize',
        action='store_true',
        help='Apply optional optimizations (remove redundant fields)'
    )
    
    args = parser.parse_args()
    
    processed, skipped, failed = process_files(
        args.files,
        dry_run=args.dry_run,
        verbose=args.verbose,
        optimize=args.optimize
    )
    
    LOG.info("=" * 60)
    LOG.info("Summary:")
    LOG.info(f"  Processed: {processed}")
    LOG.info(f"  Skipped:   {skipped}")
    LOG.info(f"  Failed:    {failed}")
    LOG.info("=" * 60)
    
    if failed > 0:
        return 1
    
    if processed == 0:
        LOG.warning("No files were processed")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())