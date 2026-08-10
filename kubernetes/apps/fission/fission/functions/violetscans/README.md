# violetscans — multi-series Fission scraper

This directory holds the shared Fission **Package** and per-series **Function**
CRs for the generic [violetscans.org](https://violetscans.org) manga scraper.

The function source lives in
[`~/personal/functions/functions/violetscans/`](https://github.com/lenaxia/functions/tree/main/functions/violetscans)
and is site-agnostic. Per-series identity (SERIES_NAME, VIOLET_URL,
KOMGA_API_KEY, ...) is supplied via a Kubernetes Secret mounted by each
Function CR; the function discovers its identity at runtime.

## Layout

```
functions/violetscans/
├── kustomization.yaml         # entry point (lists package.yaml + series/)
├── package.yaml               # single shared Fission Package CR
├── README.md                  # this file
└── series/
    ├── kustomization.yaml     # lists every series subdir
    └── <series-name>/
        ├── kustomization.yaml # lists function.yaml + secret.sops.yaml
        ├── function.yaml      # Function CR (name == series name)
        └── secret.sops.yaml   # SOPS-encrypted Secret (name == series name)

httptriggers/violetscans/      # mirror layout for HTTP + time triggers
└── series/<series-name>/
    ├── kustomization.yaml
    ├── http.yaml              # HTTPTrigger
    └── timer.yaml             # TimeTrigger
```

## Add a new series

Convention: the directory name, the Function `metadata.name`, the Secret
`metadata.name`, the Function's `secrets[].name`, and the HTTPTrigger
`relativeurl` slug must all match. Pick a short kebab-case slug for the
series and use it everywhere.

Say you want to add a series with slug `<new-series>`.

### 1. Function side

```bash
NEW=<new-series>
mkdir -p kubernetes/apps/fission/fission/functions/violetscans/series/$NEW

# Copy the may-i-please template and rename the slug in three places.
cp -r kubernetes/apps/fission/fission/functions/violetscans/series/may-i-please/* \
      kubernetes/apps/fission/fission/functions/violetscans/series/$NEW/

# Edit the new function.yaml — replace `may-i-please` everywhere:
sed -i "s/may-i-please/$NEW/g" \
    kubernetes/apps/fission/fission/functions/violetscans/series/$NEW/function.yaml

# Decrypt the copied secret, edit SERIES_NAME + VIOLET_URL, re-encrypt.
sops kubernetes/apps/fission/fission/functions/violetscans/series/$NEW/secret.sops.yaml
# In the editor:
#   - metadata.name: <new-series>
#   - stringData.SERIES_NAME: <Komga series name>
#   - stringData.VIOLET_URL: https://violetscans.org/comics/<slug>/
#   - KOMGA_* values can be kept identical to the previous series

# Register the new series.
$EDITOR kubernetes/apps/fission/fission/functions/violetscans/series/kustomization.yaml
# Add: - ./<new-series>
```

### 2. Trigger side

```bash
mkdir -p kubernetes/apps/fission/fission/httptriggers/violetscans/series/$NEW

cp -r kubernetes/apps/fission/fission/httptriggers/violetscans/series/may-i-please/* \
      kubernetes/apps/fission/fission/httptriggers/violetscans/series/$NEW/

sed -i "s/may-i-please/$NEW/g" \
    kubernetes/apps/fission/fission/httptriggers/violetscans/series/$NEW/http.yaml \
    kubernetes/apps/fission/fission/httptriggers/violetscans/series/$NEW/timer.yaml

$EDITOR kubernetes/apps/fission/fission/httptriggers/violetscans/series/kustomization.yaml
# Add: - ./<new-series>
```

### 3. Validate

```bash
# From repo root
task kubernetes:kubeconform

# Confirm the secret is encrypted before staging
grep -c "ENC\[" kubernetes/apps/fission/fission/functions/violetscans/series/$NEW/secret.sops.yaml
grep "^sops:" kubernetes/apps/fission/fission/functions/violetscans/series/$NEW/secret.sops.yaml
```

### 4. Commit & let Flux reconcile

Flux will reconcile the `fission-functions` and `fission-triggers`
Kustomizations on its next interval (or run `flux reconcile ks
fission-functions -n flux-system --with-source`).

## Package version bumps

The shared Package URL in `package.yaml` is managed by Renovate; updates to
the violetscans function code in `~/personal/functions/` should produce a new
zip artifact whose URL is then bumped here.

To bump manually:

```bash
$EDITOR kubernetes/apps/fission/fission/functions/violetscans/package.yaml
# Update spec.deployment.url to point at the new release version
```

All series share the same artifact, so a single bump rolls out to every
series simultaneously.
