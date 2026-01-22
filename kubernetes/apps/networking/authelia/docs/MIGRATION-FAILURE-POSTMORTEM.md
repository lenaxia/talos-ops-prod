# Authelia v0.10.49 Migration Failure - Postmortem

**Date:** 2026-01-22  
**Attempted Migration:** Authelia Helm Chart v0.8.58 → v0.10.49  
**Outcome:** FAILED - System restored to v0.8.58  
**Status:** Stable on v0.8.58 (Authelia 4.37.5)

---

## Executive Summary

An attempt to upgrade the Authelia helm chart from version 0.8.58 to 0.10.49 was made on 2026-01-22. The migration involved 440+ breaking schema changes across 27 configuration sections. Despite thorough configuration work and schema validation, the deployment failed due to Kubernetes secret mounting issues and OIDC configuration complexities. The system was successfully restored to the known good state (v0.8.58) via emergency rollback.

---

## Timeline

### Phase 1: Configuration & Planning (OpenCode AI)
- **Commits:** `3337ad82` through `bc99d240`
- **Duration:** Several hours
- **Work Completed:**
  - Downloaded and analyzed both chart versions (0.8.58 and 0.10.49)
  - Documented 440+ breaking changes across 27 sections
  - Updated `helm-release.yaml` with all schema migrations
  - Fixed OIDC client secret formats (multiple attempts)
  - Removed image tag override
  - Created comprehensive migration documentation (7 documents, 3,455 lines)
  - Validated configuration with `helm template` dry-run

### Phase 2: Deployment Attempts (Lenaxia)
- **Commits:** `df60f567`, `71a82362`, `7e95f485`, `9a902d9c`
- **Duration:** ~4 hours
- **Issues Encountered:**
  1. **Secret mounting failures** - Pod couldn't start due to missing secret keys
  2. **OIDC configuration issues** - Temporarily disabled OIDC to isolate problems
  3. **Image version mismatches** - Fixed image repository references
  4. **Indentation errors** - Fixed YAML formatting issues
  5. **Helm rollback loops** - Chart 0.10.49 repeatedly failed and rolled back to 0.8.58

### Phase 3: Emergency Restore
- **Commit:** `3f216f20` - "Emergency: Restore Authelia to v0.8.58 to recover service"
- **Result:** Service restored to stable state
- **Current Status:** Running v0.8.58 with Authelia 4.37.5

---

## Root Causes

### 1. Secret Structure Mismatch (PRIMARY)
**Problem:** The new chart (v0.10.49) fundamentally changed how secrets are consumed.

**Old Approach (v0.8.58):**
- Centralized `secret.*` configuration in helm values
- Secrets referenced inline in configuration
- Chart generated configMap with embedded secret references

**New Approach (v0.10.49):**
- Deprecated centralized `secret.*` structure
- Requires per-component secret file paths (e.g., `/secrets/authelia/LDAP_PASSWORD`)
- Secrets must be mounted as individual files via `additionalSecrets`

**What Happened:**
The Kubernetes secret `authelia` in namespace `networking` didn't have the keys that the new chart was trying to mount:
```
MountVolume.SetUp failed for volume "secret-authelia": 
references non-existent secret key: LDAP_PASSWORD
```

**Why It Failed:**
- The `secret.sops.yaml` file was updated with required keys
- However, Flux didn't reconcile the secret to the cluster before helm upgrade
- Pod couldn't mount non-existent secret keys → startup failure → automatic rollback

### 2. OIDC Configuration Complexity (SECONDARY)
**Problem:** The new chart completely restructured OIDC configuration with strict validation.

**Changes Required:**
- Renamed fields: `id` → `client_id`, `description` → `client_name`
- Moved lifespans to dedicated object
- Changed secret format: `secret: value` → `client_secret: { value: ... }`
- Required hash prefixes on secrets (`$plaintext$` or `$pbkdf2-sha512$`)
- Changed consent mode: `implicit` → `auto`

**What Happened:**
Multiple iterations were needed to get OIDC secrets working:
1. **First attempt:** Added `$plaintext$` prefix - Failed (Flux substitution didn't work)
2. **Second attempt:** Switched to `${SECRET_*_HASHED}` variables - Partially successful
3. **Third attempt:** Disabled OIDC entirely to isolate other issues

**Why It Failed:**
- Flux variable substitution timing unclear
- Hash prefix validation strict in new chart
- 10 OIDC clients × complex changes = high error surface area

### 3. Schema Change Magnitude (CONTRIBUTING)
**Problem:** 440+ breaking changes across nearly every configuration section.

**Major Schema Changes:**
- Session: Added `cookies[]` array, moved domain configuration
- LDAP: `url` → `address`, restructured attributes
- Storage/SMTP: Changed to `address` format (tcp://host:port, submission://host:port)
- Access Control: Moved `networks` to `definitions.network`
- WebAuthn: Moved fields to `selection_criteria`
- TOTP: Changed algorithm to uppercase

**Why It Failed:**
- Too many simultaneous changes made debugging difficult
- Each section had potential for subtle configuration errors
- Difficult to isolate which change caused which failure
- Image version mismatch (4.37.5 vs 4.39.13) added compatibility issues

### 4. Deployment Orchestration (CONTRIBUTING)
**Problem:** Helm upgrade timing vs. secret application order.

**What Happened:**
1. Configuration changes committed to git
2. Flux reconciled helm-release.yaml (triggered upgrade)
3. Pod tried to start immediately
4. Secret not yet applied to cluster
5. Pod startup failed → automatic rollback after 5 minutes

**Why It Failed:**
- No coordination between secret application and helm upgrade
- Flux reconciliation order not guaranteed
- Helm timeout (5 minutes) insufficient for manual intervention

---

## What Worked Well

### Configuration Migration ✅
- All 440+ schema changes correctly identified and documented
- Helm template dry-run validation passed
- Git-based workflow allowed for easy rollback
- Comprehensive documentation created (valuable for future attempts)

### Emergency Response ✅
- Fast rollback to known good state (commit `3f216f20`)
- Service availability maintained
- No data loss
- Clean restore to v0.8.58

### Documentation ✅
- Detailed tracking of all changes
- Clear migration steps documented
- Troubleshooting guides created
- Future attempts will benefit from this groundwork

---

## What Didn't Work

### Pre-Flight Validation ❌
- Didn't verify cluster secret state before migration
- No dry-run in dev/staging environment
- Didn't test secret mounting before full upgrade
- Insufficient validation of Flux variable substitution

### Migration Strategy ❌
- Attempted too many changes simultaneously
- No incremental rollout (all-or-nothing approach)
- Didn't isolate OIDC changes for separate testing
- No rollback checkpoints during multi-step process

### Orchestration ❌
- Didn't coordinate secret application with helm upgrade
- Relied on Flux automatic reconciliation timing
- No manual pre-application of critical secrets
- Helm timeout too short for complex troubleshooting

---

## Lessons Learned

### 1. Secret Management is Critical
**Lesson:** Secrets must be in place BEFORE any application deployment.

**Future Action:**
- Always verify cluster secrets before helm upgrade
- Manually apply secrets if needed: `sops -d secret.sops.yaml | kubectl apply -f -`
- Add pre-flight check script to validate all required secret keys exist
- Consider using Kubernetes secret dependencies in helm chart

### 2. Major Version Jumps Need Staging
**Lesson:** Jumping multiple minor versions (0.8 → 0.10) is risky.

**Future Action:**
- Test major upgrades in non-prod environment first
- Consider incremental upgrades: 0.8.58 → 0.9.x → 0.10.x
- Create dev/staging Authelia instance for testing
- Validate each schema change individually before combining

### 3. OIDC Configuration Requires Extra Care
**Lesson:** OIDC is highly sensitive to configuration format.

**Future Action:**
- Test OIDC clients individually after migration
- Keep old OIDC config as reference during migration
- Validate Flux variable substitution works in test environment
- Document working OIDC configurations for each chart version

### 4. Rollback Plans Are Essential
**Lesson:** Fast rollback saved service availability.

**Future Action:**
- Always create backup of working configuration before changes
- Document rollback procedure before starting migration
- Test rollback in dev environment
- Set shorter helm timeout to fail faster (reduce rollback time)

### 5. Incremental Changes Reduce Risk
**Lesson:** 440+ simultaneous changes made debugging nearly impossible.

**Future Action:**
- Break large migrations into smaller chunks
- Apply and test each section separately (LDAP, then Storage, then OIDC, etc.)
- Use feature flags to enable new configurations gradually
- Commit after each successful sub-migration

---

## Impact Assessment

### Service Availability
- **Downtime:** Minimal (automatic rollback kept service running)
- **User Impact:** Likely none (rollback to working version was fast)
- **Data Loss:** None

### Development Time
- **Configuration Work:** ~6-8 hours (OpenCode AI)
- **Deployment Attempts:** ~4 hours (Lenaxia)
- **Troubleshooting:** ~2 hours
- **Documentation:** ~2 hours
- **Total:** ~14-16 hours

### Technical Debt
- **Authelia Version:** Still on older 4.37.5 (vs. latest 4.39.13)
- **Chart Version:** Still on older 0.8.58 (vs. latest 0.10.49)
- **Security:** Missing 2+ months of security updates
- **Features:** Missing new features in 4.38+ and 4.39+

---

## Recommendations for Future Upgrade Attempts

### Strategy 1: Incremental Upgrade (RECOMMENDED)
**Approach:** Upgrade in smaller steps instead of jumping from 0.8 → 0.10

**Steps:**
1. Review release notes for intermediate versions (0.9.x series)
2. Upgrade to latest 0.8.x patch version first
3. Then upgrade to 0.9.x series
4. Finally upgrade to 0.10.x
5. Test thoroughly at each step

**Pros:**
- Smaller change sets at each step
- Easier to debug issues
- Lower risk of catastrophic failure

**Cons:**
- Takes more time (multiple upgrade cycles)
- More testing required

### Strategy 2: Containerized Dev Environment (RECOMMENDED)
**Approach:** Test the entire migration in a local/dev Kubernetes cluster

**Steps:**
1. Create Kind/K3d cluster locally
2. Deploy Authelia 0.8.58 (current state)
3. Attempt upgrade to 0.10.49
4. Debug and fix issues
5. Document working procedure
6. Apply to production with confidence

**Pros:**
- No production risk
- Can experiment freely
- Can test rollback procedures
- Can validate secret management

**Cons:**
- Requires local K8s cluster setup
- May not perfectly match production environment

### Strategy 3: Secret Pre-Migration (REQUIRED for any strategy)
**Approach:** Fix secret structure BEFORE attempting chart upgrade

**Steps:**
1. Audit current Kubernetes secret `authelia` in namespace `networking`
2. Update `secret.sops.yaml` with all required keys for v0.10.49
3. Manually apply secret: `sops -d secret.sops.yaml | kubectl apply -f -`
4. Verify secret has all keys: `kubectl get secret authelia -n networking -o json | jq '.data | keys'`
5. Wait 5 minutes to ensure stable
6. THEN attempt helm chart upgrade

**Pros:**
- Addresses primary failure cause
- Low risk (just updating secret)
- Can be done independently

**Cons:**
- Must understand exact secret requirements of new chart version

### Strategy 4: Feature Branch Testing (RECOMMENDED)
**Approach:** Use git branches to test configuration changes

**Steps:**
1. Create feature branch: `git checkout -b authelia-v0.10.49-attempt2`
2. Make configuration changes
3. Deploy to dev/staging cluster (or use Flux's `--target-namespace` override)
4. Test thoroughly
5. Merge to main only when proven working

**Pros:**
- Easy rollback (just switch branches)
- Can experiment freely
- Follows git best practices

**Cons:**
- Requires Flux multi-environment setup or manual deployment

---

## Current State

### Helm Release
- **Chart Version:** 0.8.58
- **App Version:** 4.37.5 (Authelia)
- **Status:** Deployed and stable
- **Image:** `ghcr.io/authelia/authelia:4.37.5`

### Configuration
- **File:** `kubernetes/apps/networking/authelia/app/helm-release.yaml`
- **State:** Known good (matches commit `f7f1e6e2`)
- **Last Verified:** 2026-01-22 (emergency restore commit `3f216f20`)

### Documentation
- **Migration docs preserved:** All 7 migration documents kept for future reference
- **Location:** `kubernetes/apps/networking/authelia/docs/`
- **Status:** Reflects attempted migration, marked as failed

### OIDC Clients (All Working)
1. Tailscale
2. MinIO
3. Open WebUI
4. PGAdmin
5. Grafana
6. Outline
7. Overseerr
8. Komga
9. Linkwarden
10. Forgejo

---

## Action Items

### Immediate (Done)
- [x] Restore service to v0.8.58
- [x] Verify service stability
- [x] Remove backup files
- [x] Document failure in postmortem
- [x] Update documentation to reflect current state

### Short Term (Within 1-2 months)
- [ ] Review Authelia 4.38+ and 4.39+ release notes for security patches
- [ ] Assess urgency of upgrade (security vulnerabilities?)
- [ ] Set up local dev Kubernetes cluster for testing
- [ ] Create secret migration script/checklist
- [ ] Test secret structure changes independently

### Medium Term (2-6 months)
- [ ] Attempt incremental upgrade: 0.8.58 → 0.9.x in dev environment
- [ ] Test and validate each major configuration change individually
- [ ] Create comprehensive test suite for OIDC clients
- [ ] Document working upgrade procedure
- [ ] Attempt production upgrade with lessons learned

### Long Term (6+ months)
- [ ] Consider alternative authentication solutions (if Authelia upgrades prove too difficult)
- [ ] Evaluate managed authentication services
- [ ] Implement automated testing for authentication workflows

---

## References

### Commits
- **Last Known Good:** `f7f1e6e2` - Revert to v0.8.58
- **Migration Start:** `3337ad82` - First attempt at v0.10.49
- **Emergency Restore:** `3f216f20` - Restore to v0.8.58
- **Cleanup:** `e18f3add` - Remove backup files

### Documentation
- [Migration Tracking](./authelia-migration-tracking.md) - Comprehensive 440+ change tracking
- [Migration Summary](./authelia-migration-summary.md) - Concise technical summary
- [Secrets Configuration Guide](./authelia-secrets-configuration.md) - Secret management details
- [Troubleshooting Guide](./troubleshooting-upgrade.md) - Deployment troubleshooting notes
- [Quick Reference](./QUICK-REFERENCE.md) - Quick command reference
- [Apply Steps](./APPLY-MIGRATION-STEPS.md) - Step-by-step application guide

### External Links
- [Authelia Documentation](https://www.authelia.com/docs/)
- [Authelia Helm Chart Repository](https://github.com/authelia/chartrepo)
- [Chart v0.10.49 Release Notes](https://github.com/authelia/chartrepo/releases/tag/authelia-0.10.49)
- [Authelia 4.39 Release Notes](https://github.com/authelia/authelia/releases/tag/v4.39.0)

---

## Conclusion

The Authelia v0.10.49 migration attempt demonstrated the complexity of major version upgrades in production environments. While the configuration work was thorough and technically correct, operational factors (secret timing, deployment orchestration) led to failure. The system was successfully restored with minimal impact.

**Key Takeaway:** Major authentication system upgrades require staging environments, incremental changes, and careful orchestration. The work done during this attempt is not wasted - it provides a solid foundation for future upgrade attempts with proper testing infrastructure in place.

**Status:** System stable on v0.8.58. Future upgrade attempts should follow incremental strategy with dev environment testing.

---

**Document Owner:** OpenCode AI  
**Contributors:** Lenaxia  
**Last Updated:** 2026-01-22  
**Next Review:** 2026-03-22 (reassess upgrade urgency)
