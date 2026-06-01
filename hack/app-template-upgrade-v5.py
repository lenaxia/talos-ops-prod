#!/usr/bin/env python3
"""
App-Template v5 Upgrade Script

This script automates the upgrade of bjw-s app-template Helm releases from v4.x to v5.0.1.

The v4→v5 upgrade is mostly a chart-version bump because the breaking changes
introduced in v5 do not affect the patterns used in this repository:

  1. rawResources restructured (manifest wrapper)        — UNUSED in this repo
  2. Default ServiceAccount auto-created                 — non-breaking, security++
  3. automountServiceAccountToken default false          — already explicitly set
  4. ServiceMonitor/PodMonitor jobLabel default change   — non-breaking, no jobLabel users
  5. NetworkPolicy controller / podSelector exclusivity  — UNUSED in this repo
  6. Min K8s 1.31  (cluster is on 1.35.3)                — satisfied
  7. Min Helm 3.18 (Flux v2.7+ ships compatible Helm)    — satisfied

The script is therefore a careful version updater that:
  - Refuses to run on files using rawResources / NetworkPolicy patterns
    that would silently break under v5.
  - Refuses to run on a file unless it is currently on a 4.x version.
  - Bumps the chart version to TARGET_VERSION.

Usage:
    python hack/app-template-upgrade-v5.py [OPTIONS] FILE [FILE ...]
    python hack/app-template-upgrade-v5.py --dry-run kubernetes/apps/**/helm-release.yaml

Options:
    --dry-run       Preview changes without writing files
    --verbose       Enable detailed logging
    --help          Show this help message
"""

import argparse
import glob
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ruamel.yaml import YAML

LOG = logging.getLogger("app-template-upgrade-v5")

TARGET_VERSION = "5.0.1"
HELM_RELEASE_NAMES = ["helmrelease.yaml", "helm-release.yaml"]
# Suffixes/patterns to also accept (e.g., subgen has worker-helm-release.yaml +
# orchestrator-helm-release.yaml, ragnarok has test.yaml). The is_app_template_release
# check verifies the file actually contains an app-template HelmRelease, so
# accepting more filenames is safe.
HELM_RELEASE_SUFFIXES = ["-helm-release.yaml", "-helmrelease.yaml"]
HELM_RELEASE_EXTRA = ["test.yaml"]


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    LOG.setLevel(level)

    if not LOG.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        LOG.addHandler(handler)


def load_yaml_file(filepath: Path) -> Any:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    with open(filepath, "r") as file:
        return yaml.load(file)


def save_yaml_file(filepath: Path, data: Any) -> None:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    with open(filepath, "w") as file:
        yaml.dump(data, file)


def get_nested_value(data: Dict, path: str) -> Optional[Any]:
    value = data
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def is_app_template_release(data: Dict) -> bool:
    return (
        data.get("kind") == "HelmRelease"
        and get_nested_value(data, "spec.chart.spec.chart") == "app-template"
    )


def get_current_version(data: Dict) -> Optional[str]:
    return get_nested_value(data, "spec.chart.spec.version")


def detect_blocking_v5_patterns(data: Dict) -> List[str]:
    """Return human-readable reasons this file cannot be auto-upgraded to v5.

    These are the patterns whose semantics change in v5 and would require
    a manual rewrite of the values. If any are found, the script will
    refuse to upgrade the file and ask the operator to handle it manually.
    """
    issues: List[str] = []
    values = get_nested_value(data, "spec.values") or {}

    # 1. rawResources moved into a `manifest:` wrapper
    raw_resources = values.get("rawResources")
    if isinstance(raw_resources, dict) and raw_resources:
        for name, cfg in raw_resources.items():
            if isinstance(cfg, dict) and "manifest" not in cfg:
                issues.append(
                    f"rawResources/{name} uses the v4 layout (no `manifest:` wrapper) "
                    f"— move spec contents under `manifest:` and labels/annotations under "
                    f"`manifest.metadata` per the v4→v5 upgrade guide."
                )

    # 2. NetworkPolicy `controller` and `podSelector` are now mutually exclusive
    network_policies = values.get("networkpolicies") or values.get("networkPolicies")
    if isinstance(network_policies, dict):
        for name, cfg in network_policies.items():
            if isinstance(cfg, dict) and "controller" in cfg and "podSelector" in cfg:
                issues.append(
                    f"networkpolicies/{name} sets BOTH `controller` and `podSelector` "
                    f"— v5 makes these mutually exclusive. Pick one."
                )

    return issues


def should_process_file(filepath: Path, data: Dict) -> Tuple[bool, str]:
    if not is_app_template_release(data):
        return False, "Not an app-template HelmRelease"

    current_version = get_current_version(data)
    if not current_version:
        return False, "Could not determine current version"

    if current_version.startswith("5."):
        return False, f"Already on v5.x ({current_version})"

    if current_version.startswith("3."):
        return False, (
            f"Version {current_version} requires v3→v4 upgrade first "
            f"(use app-template-upgrade-v4.py)"
        )

    if current_version.startswith("2."):
        return False, (
            f"Version {current_version} requires v2→v3 then v3→v4 first "
            f"(use app-template-upgrade-v3.py and v4 first)"
        )

    if not current_version.startswith("4."):
        return False, f"Unexpected version: {current_version}"

    blockers = detect_blocking_v5_patterns(data)
    if blockers:
        return False, "Manual migration required: " + "; ".join(blockers)

    return True, f"Ready to upgrade from {current_version} to {TARGET_VERSION}"


def upgrade_file(filepath: Path, dry_run: bool = False) -> Tuple[bool, List[str]]:
    changes: List[str] = []

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

    data["spec"]["chart"]["spec"]["version"] = TARGET_VERSION
    changes.append(f"Updated chart version: {current_version} → {TARGET_VERSION}")

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
    file_patterns: List[str], dry_run: bool = False, verbose: bool = False
) -> Tuple[int, int, int]:
    setup_logging(verbose)

    all_files: List[str] = []
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
    LOG.info("")

    processed = skipped = failed = 0
    blocked: List[Tuple[str, str]] = []

    for filepath_str in all_files:
        filepath = Path(filepath_str)

        is_release_filename = (
            filepath.name in HELM_RELEASE_NAMES
            or filepath.name in HELM_RELEASE_EXTRA
            or any(filepath.name.endswith(s) for s in HELM_RELEASE_SUFFIXES)
        )
        if not is_release_filename:
            LOG.debug(f"Skipping {filepath}: not a helm-release file")
            skipped += 1
            continue

        success, changes = upgrade_file(filepath, dry_run)

        if success:
            processed += 1
            for change in changes:
                LOG.info(f"  {change}")
            LOG.info("")
        elif changes:
            skipped += 1
            reason = changes[0]
            if reason.startswith("Manual migration required"):
                blocked.append((str(filepath), reason))
            if verbose:
                LOG.debug(f"  {reason}")
        else:
            failed += 1

    if blocked:
        LOG.warning("")
        LOG.warning(f"⚠ {len(blocked)} file(s) need manual migration before v5:")
        for path, reason in blocked:
            LOG.warning(f"  {path}")
            LOG.warning(f"    → {reason}")

    return processed, skipped, failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upgrade bjw-s app-template Helm releases from v4.x to v5.0.1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single file with dry-run
  %(prog)s --dry-run kubernetes/apps/media/bazarr/app/helm-release.yaml

  # Whole tree
  %(prog)s --dry-run kubernetes/apps/**/helm-release.yaml

  # Verbose mode for debugging
  %(prog)s --verbose --dry-run kubernetes/apps/home/frigate/app/helm-release.yaml
""",
    )
    parser.add_argument("files", nargs="+", help="Files or glob patterns to process")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without writing files"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable detailed logging"
    )

    args = parser.parse_args()

    processed, skipped, failed = process_files(
        args.files, dry_run=args.dry_run, verbose=args.verbose
    )

    LOG.info("")
    LOG.info("=" * 60)
    LOG.info(f"Summary: {processed} updated, {skipped} skipped, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
