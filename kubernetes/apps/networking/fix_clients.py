#!/usr/bin/env python3
import re
import sys


def fix_clients(file_path):
    with open(file_path, "r") as f:
        content = f.read()

    # Pattern to match each client block
    # Each client starts with "- id:" and continues until the next "- id:" or end of clients section
    client_pattern = r"(\s*-\s*id:\s*[^\n]+(?:\n\s*[^-].*)*)"

    # Find the clients section
    clients_section_match = re.search(
        r"clients:(.*?)(?=\n\s*\w+:|$)", content, re.DOTALL
    )
    if not clients_section_match:
        print("Could not find clients section")
        return

    clients_section = clients_section_match.group(1)

    # Split into individual clients
    clients = re.findall(client_pattern, clients_section, re.DOTALL)

    print(f"Found {len(clients)} clients")

    # Process each client
    for i, client in enumerate(clients):
        print(f"\nProcessing client {i + 1}:")

        # Add claims_policy if not present
        if "claims_policy:" not in client:
            # Find authorization_policy line and add claims_policy after it
            client = re.sub(
                r"(authorization_policy:\s*[^\n]+)",
                r"\1\n             claims_policy: \'backward_compat\'",
                client,
            )
            print("  Added claims_policy")

        # Remove userinfo_signing_algorithm if present
        if "userinfo_signing_algorithm:" in client:
            client = re.sub(r"\n\s*userinfo_signing_algorithm:\s*[^\n]+", "", client)
            print("  Removed userinfo_signing_algorithm")

        # Fix indentation - ensure all lines have consistent indentation
        lines = client.strip().split("\n")
        fixed_lines = []
        for j, line in enumerate(lines):
            if j == 0:  # First line (with - id:)
                # Ensure it has 12 spaces before the dash
                line = re.sub(r"^\s*", "           ", line)
            else:
                # Ensure it has 14 spaces
                line = re.sub(r"^\s*", "             ", line)
            fixed_lines.append(line)

        clients[i] = "\n".join(fixed_lines)

    # Reconstruct the clients section
    fixed_clients_section = "\n" + "\n".join(clients)

    # Replace the old clients section with the fixed one
    fixed_content = re.sub(
        r"(clients:).*?(?=\n\s*\w+:|$)",
        r"\1" + fixed_clients_section,
        content,
        flags=re.DOTALL,
    )

    # Write back to file
    with open(file_path, "w") as f:
        f.write(fixed_content)

    print(f"\nFixed {len(clients)} clients in {file_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <yaml_file>")
        sys.exit(1)

    fix_clients(sys.argv[1])
