import os
import ruamel.yaml
import argparse
import logging
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configurable values
OLD_SOURCE_REF_NAME = 'home-ops'
NEW_SOURCE_REF_NAME = 'home-kubernetes'
OLD_PATH_PREFIX = './cluster/'
NEW_PATH_PREFIX = './kubernetes/'

def find_ks_yaml_files(root_dir):
    """Recursively find all ks.yaml files in the given root directory."""
    ks_yaml_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file == 'ks.yaml':
                ks_yaml_files.append(os.path.join(root, file))
    return ks_yaml_files

def update_ks_yaml(file_path, dry_run=False, verbose=False):
    """Update the sourceRef.name and path fields in the given ks.yaml file."""
    changes_made = []
    yaml = ruamel.yaml.YAML()
    yaml.preserve_quotes = True
    yaml.explicit_start = True
    yaml.explicit_end = False  # Omit the '...' document end marker
    yaml.width = None
    yaml.indent(mapping=2, sequence=4, offset=2)

    try:
        with open(file_path, 'r') as stream:
            docs = list(yaml.load_all(stream))
    except ruamel.yaml.parser.ParserError as e:
        logger.error(f"Error parsing {file_path}: {e}")
        return changes_made

    valid_docs = []  # Collect valid, non-empty documents
    for idx, doc in enumerate(docs):
        if doc is None:
            continue
        if doc.get('kind') == 'Kustomization':
            if 'sourceRef' in doc['spec'] and doc['spec']['sourceRef']['name'] == OLD_SOURCE_REF_NAME:
                if not dry_run:
                    doc['spec']['sourceRef']['name'] = NEW_SOURCE_REF_NAME
                changes_made.append(f'Updated sourceRef.name from "{OLD_SOURCE_REF_NAME}" to "{NEW_SOURCE_REF_NAME}" in Kustomization {doc["metadata"]["name"]}')
                if verbose:
                    logger.info(f'In {file_path}: {changes_made[-1]}')

            if 'path' in doc['spec']:
                old_path = doc['spec']['path']
                new_path = old_path.replace(OLD_PATH_PREFIX, NEW_PATH_PREFIX)
                if old_path != new_path:
                    if not dry_run:
                        doc['spec']['path'] = new_path
                    changes_made.append(f'Updated path from "{old_path}" to "{new_path}" in Kustomization {doc["metadata"]["name"]}')
                    if verbose:
                        logger.info(f'In {file_path}: {changes_made[-1]}')

        valid_docs.append(doc)

    if not dry_run:
        try:
            with open(file_path, 'w') as stream:
                yaml.dump_all(valid_docs, stream)
        except YAMLError as e:
            logger.error(f"Error writing to {file_path}: {e}")
            return []

    return changes_made

def generate_report(changes, report_file='migration_report.txt'):
    """Generate a report of the changes made and write it to a file."""
    report = "Migration Report:\n\n"
    if not changes:
        report += "No changes would be made to any ks.yaml files.\n"
    else:
        mode = "would be made" if any(file_changes for file_changes in changes.values()) else "were made"
        report += f"The following changes {mode}:\n"
        for file, file_changes in changes.items():
            report += f"\n{file}:\n"
            for change in file_changes:
                report += f"  - {change}\n"

    with open(report_file, 'w') as f:
        f.write(report)

    logger.info(f"Report generated and saved to {report_file}")

def main(root_dir, dry_run=False, verbose=False):
    """Main function to find, update files, and generate a report."""
    changes = {}
    ks_yaml_files = find_ks_yaml_files(root_dir)

    for file_path in ks_yaml_files:
        logger.info(f"Processing file: {file_path}")
        file_changes = update_ks_yaml(file_path, dry_run, verbose)
        if file_changes:
            changes[file_path] = file_changes

    if dry_run:
        logger.info("Dry run mode: No changes were applied.")
    else:
        logger.info("Changes applied to all files.")

    generate_report(changes, 'dry_migration_report.txt' if dry_run else 'migration_report.txt')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script to update ks.yaml files in a GitOps repo.")
    parser.add_argument('-r', '--root', default='.', help="Root directory of the GitOps repo")
    parser.add_argument('-d', '--dry', action='store_true', help="Dry run mode: only show changes that would be made")
    parser.add_argument('-v', '--verbose', action='store_true', help="Verbose mode: show detailed output during processing")

    args = parser.parse_args()
    main(args.root, args.dry, args.verbose)
