# GitHub PR Review Workflow Prompt

## Variables to Customize

- `{OWNER}`: lenaxia
- `{REPO}`: talos-ops-prod
- `{LIST_EXCLUDED_APPS}`: Authelia, Traefik

## Notes

- Never use or upgrade Bitnami charts as they have revoked all open source helm charts
- MinIO has deprecated all of their opensource repos and have become open source hostile
- The App-template helm chart is based off of Bjw-s Common Library helm chart, documentation for both can be found here https://bjw-s-labs.github.io/helm-charts/docs/ and should be used when doing major upgrades

## Objective
Review and merge pull requests from a GitHub repository systematically, with special attention to version changes and breaking changes.

## Instructions

Please review all open pull requests for the repository: `https://github.com/{OWNER}/{REPO}/pulls`

### Workflow Steps

1. **Fetch all open PRs** using the GitHub MCP server
2. **Create a tracking document** (`./.tmp/YYYY-MM-DD-pr-review-checklist.md`) with all PRs listed
3. **Review each PR systematically** following these rules:

### Review Rules by Update Type

#### Patch Updates (x.x.X)
- **Action**: Merge immediately
- **Reason**: Bug fixes and security patches only
- **Verification**: Check files changed to ensure it's truly a patch

#### Digest Updates
- **Action**: Merge immediately  
- **Reason**: Commit hash updates are always safe
- **Verification**: Confirm it's just a digest/SHA update

#### Minor Updates (x.X.x)
- **Action**: Review changelog, then merge if safe
- **Process**:
  1. Get the PR files to understand what's being updated
  2. Extract the old and new versions from the PR title/body
  3. Use GitHub MCP server to fetch release notes between versions:
     - For GitHub Actions: Check the action's repository releases
     - For container images: Check the source repository releases
  4. Analyze release notes for:
     - Breaking changes (even in minor versions)
     - Deprecated features
     - New required parameters
     - Behavioral changes that could affect your usage
  5. If no breaking changes found: Merge
  6. If breaking changes found: Document in checklist and skip for manual review

#### Major Updates (X.x.x)
- **Action**: Thorough review required
- **Process**:
  1. Get the PR files to understand scope of changes
  2. Extract version information from PR
  3. Use GitHub MCP server to fetch comprehensive release notes:
     - Get all releases between old and new version
     - Pay special attention to BREAKING CHANGES sections
     - Look for migration guides
     - Check for deprecated/removed features
  4. Analyze impact on your codebase:
     - Check which files are affected
     - Determine if breaking changes apply to your usage
     - Identify if any code changes are needed
  5. Decision matrix:
     - **No breaking changes OR breaking changes don't affect us**: Merge
     - **Breaking changes affect us**: Document required actions, skip for manual review
     - **Unclear impact**: Skip for manual review with notes

#### Configuration Updates
- **Action**: Review changes, merge if safe
- **Process**: Check diff to ensure no unintended changes

### Special Exclusions

**DO NOT merge PRs related to:**
- {LIST_EXCLUDED_APPS} (e.g., "Authelia", "Traefik")
- Any PR with "abandoned" in the title
- PRs with abnormally high commit counts (>100 commits for a simple update)

### Error Handling

- **"Head branch is out of date"**: Skip for now, will auto-update or handle later
- **Merge conflicts**: Skip for manual resolution
- **Failed CI checks**: Skip for manual review

### Tracking

Update the checklist document after each PR with:
- ✅ MERGED - with decision reasoning
- ❌ CLOSED - with reason
- ⏳ NEEDS REVIEW - with specific concerns
- 🔄 SKIPPED - with reason (out of date, conflicts, etc.)

### Example GitHub MCP Commands

```javascript
// List all open PRs
use_mcp_tool: github/list_pull_requests
{
  "owner": "owner-name",
  "repo": "repo-name", 
  "state": "open",
  "perPage": 100
}

// Get PR details
use_mcp_tool: github/get_pull_request
{
  "owner": "owner-name",
  "repo": "repo-name",
  "pullNumber": 123
}

// Get files changed in PR
use_mcp_tool: github/get_pull_request_files
{
  "owner": "owner-name",
  "repo": "repo-name",
  "pullNumber": 123
}

// Get release notes (for actions/checkout example)
use_mcp_tool: github/get_release_by_tag
{
  "owner": "actions",
  "repo": "checkout",
  "tag": "v6.0.0"
}

// List releases between versions
use_mcp_tool: github/list_releases
{
  "owner": "actions",
  "repo": "checkout",
  "perPage": 20
}

// Merge PR
use_mcp_tool: github/merge_pull_request
{
  "owner": "owner-name",
  "repo": "repo-name",
  "pullNumber": 123,
  "merge_method": "squash"
}

// Close PR
use_mcp_tool: github/update_pull_request
{
  "owner": "owner-name",
  "repo": "repo-name",
  "pullNumber": 123,
  "state": "closed"
}
```

### Enhanced Release Notes Analysis

For each minor and major version update:

1. **Identify the source repository**
   - For GitHub Actions: Extract owner/repo from action path (e.g., `actions/checkout`)
   - For container images: Check the PR body for links to source repo
   - For other dependencies: Look in PR description or files changed

2. **Fetch release information**
   ```javascript
   // Get specific release
   use_mcp_tool: github/get_release_by_tag
   {
     "owner": "source-owner",
     "repo": "source-repo",
     "tag": "v{NEW_VERSION}"
   }
   
   // Or list recent releases to find the range
   use_mcp_tool: github/list_releases
   {
     "owner": "source-owner",
     "repo": "source-repo",
     "perPage": 50
   }
   ```

3. **Analyze release notes for**:
   - **BREAKING CHANGES** section
   - **Breaking Changes** heading
   - Words like "breaking", "removed", "deprecated", "incompatible"
   - Migration guides or upgrade instructions
   - Changes to default behavior
   - New required parameters or configuration
   - Removed features or APIs

4. **Cross-reference with your usage**:
   - Check the files changed in the PR
   - Determine if breaking changes affect those specific files
   - Look for usage patterns that might be impacted

5. **Document findings**:
   ```markdown
   ### PR #X - package vOLD → vNEW
   - **Breaking Changes Found**: 
     - Change 1: Description and impact
     - Change 2: Description and impact
   - **Applies to us**: YES/NO
   - **Required actions**: List any code changes needed
   - **Decision**: MERGE / NEEDS_MANUAL_REVIEW
   ```

### Output

Create a final summary document with:
- located at `./tmp/YYYY-MM-DD-pr-merge-summary.md`
- Total PRs reviewed
- PRs merged (with brief reasoning)
- PRs closed (with reasoning)
- PRs requiring manual review (with specific concerns)
- Any PRs skipped due to exclusions

## Notes

- This workflow prioritizes safety over speed for major updates
- Always document reasoning for merge decisions
- When in doubt, skip for manual review rather than auto-merging
- The GitHub MCP server provides rich release information - use it!