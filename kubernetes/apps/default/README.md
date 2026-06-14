# Shadow Testing Environment

This directory contains shadow instances for testing major version upgrades before applying them to production.

**Namespace:** `default`

## Components

### Echo Server Shadow (Test Application)
- **Purpose:** Validate authentication flow through shadow instances

**Files:**
- [`echo-server-shadow/ks.yaml`](echo-server-shadow/ks.yaml)
- [`echo-server-shadow/app/helm-release.yaml`](echo-server-shadow/app/helm-release.yaml)
- [`echo-server-shadow/app/kustomization.yaml`](echo-server-shadow/app/kustomization.yaml)

> **Note:** A `traefik-shadow` instance previously lived in this directory for the
> v2→v3 chart upgrade test and has since been removed (production migrated to Traefik v3).
> An `authelia-shadow` instance was also present for the v4.37→v4.39 migration test but
> was removed after the migration failed.
