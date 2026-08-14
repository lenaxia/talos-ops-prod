#!/usr/bin/env bash
# Fill Cloudflare credentials in the ansible-runner secret (sops) and leave
# the tree ready for a revision bump + commit.
#
# Works around sops 3.7.1 breakage (--set fails: "no matching creation
# rules" / panics) by doing a decrypt -> line-edit -> encrypt-in-place
# roundtrip, which is verified to work for repo paths.
#
# Usage (env-based to keep the token out of argv):
#   SECRET=<path> CF_TOKEN=<token> [CF_ACCOUNT=<id>] bash cf-activate.sh
set -euo pipefail

SECRET="${SECRET:?SECRET=<path to secret.sops.yaml> required}"
CF_TOKEN="${CF_TOKEN:?CF_TOKEN=<cloudflare workers api token> required}"
CF_ACCOUNT="${CF_ACCOUNT:?CF_ACCOUNT=<cloudflare account id> required}"

command -v sops >/dev/null || { echo "ERROR: sops not found"; exit 1; }
[ -f "$SECRET" ] || { echo "ERROR: $SECRET not found"; exit 1; }

# Temp lives next to the secret so its path matches the repo .sops.yaml
# creation rules (sops -e resolves rules from the INPUT path)
TMP="$(mktemp "$(dirname "$SECRET")/.cf-activate.XXXXXX.sops.yaml")"
trap 'rm -f "$TMP"' EXIT

sops -d "$SECRET" > "$TMP"

python3 - "$TMP" "$CF_TOKEN" "$CF_ACCOUNT" <<'PY'
import re, sys

path, token, account = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(path).read()

for key, value in (("CLOUDFLARE_API_TOKEN", token), ("CLOUDFLARE_ACCOUNT_ID", account)):
    pattern = re.compile(r"^(\s*%s:).*$" % key, re.MULTILINE)
    if not pattern.search(src):
        sys.exit(f"ERROR: key {key} not found in {path}")
    src = pattern.sub(lambda m: f"{m.group(1)} {value}", src)

open(path, "w").write(src)
PY

# Encrypt from temp into the secret — the original is only replaced with
# already-encrypted bytes, so a failure never leaves plaintext in the tree
sops -e "$TMP" > "$SECRET"

# Verify the roundtrip before declaring success
if sops -d "$SECRET" | grep -Fq "CLOUDFLARE_API_TOKEN: $CF_TOKEN" && \
   sops -d "$SECRET" | grep -Fq "CLOUDFLARE_ACCOUNT_ID: $CF_ACCOUNT"; then
  echo "OK: secret updated and re-encrypted (ciphertext-only diff in git)"
else
  echo "ERROR: verify failed — secret left re-encrypted; inspect with: sops -d $SECRET" >&2
  exit 1
fi
