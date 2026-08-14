# Worklog: Ansible offline-Pi tolerance + serial DNS applies

**Date:** 2026-08-14
**Status:** Deployed to main (ansible-runner job)

## Problem

1. The ansible-runner Job failed whenever any fleet Pi was powered off
   (`kiosk01`, `pikvm01`, `spare01`, `voice01` routinely are) — unreachable
   hosts return exit code 4 and the Job retried until backoffLimit.
2. DNS config changes applied to all `dns` hosts in one play. A bad change
   or simultaneous blocky restart could take down both resolvers at once.
   (Seen in the wild: the split-horizon `thekao.cloud` mapping shipped in
   9934911d and broke LLMSafeSpaces workspace egress for ~24h.)

## Changes

- `ansible.cfg` (+ runner configmap): `ignore_unreachable = True` —
  unreachable hosts no longer fail the run; real task failures still do.
- `playbooks/site.yaml`: DNS play (`dns` + `loadbalancer` roles) split out
  and runs with `serial: 1`.
- `playbooks/dns.yaml`: same `serial: 1`.
- `roles/dns/tasks/quorum_preflight.yaml` (+ `quorum_check_sibling.yaml`):
  before touching a DNS node, every sibling in the `dns` group must pass
  TCP/53 + a live query for `dns_health_check_name` (default
  `cloudflare.com`, via `lookup('dig', '@<resolver>')` from the
  controller). If any sibling is down the play aborts — we never restart
  the last healthy resolver.
- `roles/dns/tasks/verify.yaml`: after handlers flush, the node just
  changed must pass TCP/53 + a live query before the serial play may move
  to the next node.
- Runner entrypoints install `dnspython` so the `dig` lookup works.

## Validation

- `--syntax-check` clean for site.yaml, dns.yaml, update.yaml.
- `lookup('dig', 'cloudflare.com', '@192.168.0.5')` returns A records;
  dead IP returns `''` (caught as unhealthy).
- UDP/53 from a `home` namespace pod to the LAN resolvers verified working
  (dnstest pod).
- ansible-runner Job completed green with 4 fleet hosts unreachable.

## Operational notes

- If both resolvers must be redeployed from scratch, remove `serial: 1`
  temporarily or run the play with `--limit` per host.
- Job exit code stays 0 for unreachable-only runs; check the recap in the
  logs for which hosts were skipped.
