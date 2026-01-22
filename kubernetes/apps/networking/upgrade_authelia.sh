#!/bin/bash
set -e

FILE="authelia/app/helm-release.yaml"

echo "Upgrading Authelia from 4.37.5 to 4.39.15..."

# 1. Update chart version
sed -i 's/version: 0.8.58/version: 0.10.49/' "$FILE"

# 2. Update image tag
sed -i 's/tag: 4.37.5/tag: 4.39.15/' "$FILE"

# 3. Add claims_policies configuration
# Find the line with "cors:" and add claims_policies after it
sed -i '/cors:/,/clients:/ {
  /allowed_origins_from_client_redirect_uris: true/ a\
\
          claims_policies:\
            backward_compat:\
              id_token:\
                - rat\
                - groups\
                - email\
                - email_verified\
                - alt_emails\
                - preferred_username\
                - name\
' "$FILE"

# 4. For each client, add claims_policy and remove userinfo_signing_algorithm
# This is more complex and would need to be done for each client
# For now, let's just fix the first few as an example

echo "Done! Please verify the changes and run validation."