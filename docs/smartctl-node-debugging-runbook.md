# Runbook: Reading SMART data from Talos nodes with debug pods

Investigated 2026-08-15 after a burst of failing `node-debugger-worker-02-*`
pods in namespace `home` (fingerprint `f8d8bcabe2bf`).

## Symptom

Ad-hoc `kubectl debug node/worker-02` pods terminate with
`container debugger: terminated with exit code 1` (or `2`), e.g.
`node-debugger-worker-02-g4bv9`:

```
Command:  sh -c 'apk add --no-cache smartmontools >/dev/null 2>&1; smartctl -H -A -i /host/dev/nvme0n1'
State:    Terminated (Error), Exit Code 1
Mounts:   /host from host-root (rw)   # hostPath: /
```

## Root cause

`kubectl debug node/...` pods created without a privileged profile have **no
`securityContext`**. Unprivileged containers cannot open host block device
nodes reached through the `/host` hostPath mount — access is denied by the
container runtime's device allowlist (EPERM), regardless of the pod mounting
`/`. `smartctl` then fails with:

- exit `2` — bit 1: *device open failed* (seen with `nixery.dev/smartmontools`)
- exit `1` — open/parse failure variant (seen with alpine + `apk add smartmontools`)
- exit `127` — smartctl not installed (e.g. `chroot /host` — Talos has no apk)

None of these indicate a failing disk. A SMART health failure would set bit 3
(exit code 8+). Observed exit codes were purely tooling/access failures.

Note: pods whose command ends with `cat`/`ls`/`which` report `Completed`
because those commands mask smartctl's exit status — a green checkmark on the
pod does **not** mean the SMART read succeeded.

## Correct procedure

1. Preferred, no pod at all (disk inventory):

   ```
   talosctl disks -n worker-02
   ```

2. Privileged debug pod (required for `smartctl`):

   ```
   kubectl debug node/worker-02 -n home \
     --image=alpine:latest \
     --profile=legacy \
     -- sh -c 'apk add --no-cache smartmontools >/dev/null 2>&1; smartctl -H -A -i /host/dev/nvme0n1'
   ```

   `--profile=legacy` is the critical part — it sets `privileged: true`, which
   is needed to open `/host/dev/nvme0n1`. Without it the run fails with exit
   1/2 as described above.

3. Verify the run actually worked: the pod exits `0` **and** the log output
   starts with `smartctl 7.x` — not with `Unable to open device`.

## Cleanup

`kubectl debug` pods are never garbage-collected. After use, delete them:

```
kubectl -n home delete pod -l 'name in (node-debugger-worker-02-xxxxx)'
# or all stale debugger pods:
kubectl -n home get pods -o name | grep node-debugger | xargs kubectl -n home delete
```

(As of 2026-08-15 there are 13 stale `node-debugger-*` pods in `home`, the
oldest 173 days old.)
