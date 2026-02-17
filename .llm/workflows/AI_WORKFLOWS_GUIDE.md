# Comprehensive Guide: AI-Powered Workflows for Infrastructure Repositories

This guide explains how to replicate the AI-powered workflows used in this Talos Kubernetes cluster repository. These workflows automate issue triage, PR review, Renovatebot analysis, and failure analysis using the OpenCode CLI.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites & Setup](#prerequisites--setup)
3. [Core Concepts](#core-concepts)
4. [Issue Responder Workflow](#issue-responder-workflow)
5. [Renovate PR Analyzer Workflow](#renovate-pr-analyzer-workflow)
6. [Failure Analysis Workflow](#failure-analysis-workflow)
7. [Prompt Engineering Best Practices](#prompt-engineering-best-practices)
8. [Common Patterns](#common-patterns)
9. [Key Learnings & Gotchas](#key-learnings--gotchas)
10. [Troubleshooting](#troubleshooting)

## Architecture Overview

The AI workflows follow this pattern:

```
GitHub Event → GitHub Action → Context Collection → OpenCode CLI → AI Analysis → Actions (PRs, Comments, etc.)
```

**Key Components:**

- **GitHub Actions**: Trigger workflows on events (issues, PRs, workflow failures)
- **OpenCode CLI**: AI analysis engine with local/self-hosted model support
- **Embedded Prompts**: Detailed instructions embedded in YAML workflow files
- **gh CLI**: Used for GitHub API interactions (fetching context, creating resources)
- **No TypeScript SDK**: Direct CLI invocation, no compiled scripts needed

**Why This Approach?**

- **Simplicity**: Everything in one YAML file, no separate scripts to maintain
- **Flexibility**: Easy to modify prompts without rebuilding anything
- **Infrastructure-friendly**: Perfect for GitOps repos where you want visibility into all logic
- **Self-hosted**: Works with your own OpenAI-compatible endpoints

## Prerequisites & Setup

### 1. Required Secrets

```bash
# Required secrets in your repository:
OPENAI_API_KEY=your_api_key              # OpenAI-compatible API key
OPENAI_API_BASE=https://your-llm-endpoint  # Your OpenAI-compatible endpoint
OPENAI_MODEL=vllm-local/default           # Model identifier (optional, can default)

# GitHub provides these automatically:
GITHUB_TOKEN=${{ secrets.GITHUB_TOKEN }}   # Auto-provided, no setup needed
```

### 2. Repository Structure

```
.github/
├── workflows/
│   ├── issue-responder.yml      # Main issue/PR comment handler
│   ├── renovate-analysis.yml    # Renovatebot PR analyzer
│   └── failure-analysis.yml    # Workflow failure analyzer
└── actions/
    └── setup-bun/               # Shared setup action (optional, for tooling)
```

### 3. Setup Bun Action (Optional)

If you need Bun for any tools:

```yaml
# .github/actions/setup-bun/action.yml
name: 'Setup Bun'
description: 'Setup Bun with cache'
runs:
  using: 'composite'
  steps:
    - name: Setup Bun
      uses: oven-sh/setup-bun@v2
      with:
        bun-version: latest
    
    - name: Cache dependencies
      uses: actions/cache@v4
      with:
        path: ~/.bun/install/cache
        key: ${{ runner.os }}-bun-${{ hashFiles('**/bun.lock') }}
        restore-keys: |
          ${{ runner.os }}-bun-
    
    - name: Install dependencies
      shell: bash
      run: |
        if [ -f "package.json" ]; then
          bun install --frozen-lockfile || bun install
        else
          echo "No package.json found, skipping dependency installation"
        fi
```

### 4. OpenCode CLI Installation Pattern

All workflows use this standard installation pattern:

```yaml
- name: Install OpenCode CLI
  run: |
    curl -fsSL https://opencode.ai/install | bash
    echo "$HOME/.opencode/bin" >> $GITHUB_PATH
```

**Key Points:**
- Uses the official install script
- Adds to PATH so subsequent steps can use it
- No npm package installation needed

## Core Concepts

### 1. Embedded Prompts vs Separate Scripts

**This repository uses EMBEDDED PROMPTS** - the entire AI instruction is in the YAML workflow file, not in separate TypeScript scripts.

**Why Embedded Prompts?**

```yaml
# Good - Embedded (this repo's approach)
- name: Analyze with OpenCode
  run: |
    opencode run <<'PROMPT_EOF'
    You are an AI assistant that...
    [Full prompt here]
    PROMPT_EOF
```

**Benefits:**
- Single file to review and understand
- Easy to modify prompts
- No build process
- All logic visible in the PR diff

### 2. Self-Hosted LLM Integration

Workflows use `OPENAI_API_BASE` to point to self-hosted models:

```yaml
env:
  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  OPENAI_API_BASE: ${{ secrets.OPENAI_API_BASE }}
  OPENAI_MODEL: ${{ secrets.OPENAI_MODEL }}
```

Then invoke OpenCode CLI:

```bash
# Using specified model
opencode run -m vllm-local/default "$(cat .tmp/prompt.txt)"

# Or use default from environment
opencode run "$(cat .tmp/prompt.txt)"
```

### 3. Context Collection Pattern

Before invoking AI, collect all relevant context:

```yaml
- name: Collect context
  run: |
    # Get issue/PR details
    ISSUE_INFO=$(gh issue view "$ISSUE_NUMBER" --json body,comments)
    
    # Get files changed
    CHANGED_FILES=$(gh pr diff "$PR_NUMBER" --name-only)
    
    # Build context
    cat > .tmp/context.txt <<EOF
    Issue: $ISSUE_INFO
    Files Changed: $CHANGED_FILES
    EOF
    
    # Pass context to AI
    opencode run "$(cat .tmp/context.txt)"
```

### 4. Tool Usage Enforcement

**CRITICAL**: The AI must be explicitly told to use tools:

```yaml
# In prompt, explicitly require tool calls:
CRITICAL RULES:
1. ALWAYS use the github_add_issue_comment tool to post responses
2. NEVER output text as the response - must call the tool
3. Outputting text ≠ posting comment
```

**Why?** Without explicit instructions, AI tends to just output text instead of calling tools.

## Issue Responder Workflow

This is the foundational workflow that handles both issues and PR comments.

### Full Workflow Structure

```yaml
name: Issue Responder

on:
  issues:
    types: [opened]
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

jobs:
  issue-responder:
    if: |
      github.event.sender.login == 'lenaxia' &&
      (github.event_name == 'issues' ||
       (github.event_name == 'issue_comment' && github.event.issue.pull_request == null) ||
       (github.event_name == 'issue_comment' && github.event.issue.pull_request != null && startsWith(github.event.comment.body, '/ai')) ||
       (github.event_name == 'pull_request_review_comment' && startsWith(github.event.comment.body, '/ai')))
    
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
      pull-requests: write
    
    steps:
      - name: Determine checkout ref
        id: determine-ref
        if: github.event_name == 'issue_comment' && github.event.issue.pull_request != null
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # For PRs, checkout the PR's branch (not main)
          PR_NUMBER="${{ github.event.issue.number }}"
          PR_DATA=$(gh pr view "${PR_NUMBER}" --json headRefName,headRepository --repo ${{ github.repository }})
          PR_BRANCH=$(echo "$PR_DATA" | jq -r '.headRefName')
          REPO_NAME=$(echo "$PR_DATA" | jq -r '.headRepository.nameWithOwner')

          if [[ "$REPO_NAME" == "${{ github.repository }}" ]]; then
            echo "checkout-ref=${PR_BRANCH}" >> $GITHUB_OUTPUT
          else
            echo "checkout-ref=main" >> $GITHUB_OUTPUT
          fi

      - name: Checkout repository
        uses: actions/checkout@v6
        with:
          ref: ${{ steps.determine-ref.outputs.checkout-ref || 'main' }}
          fetch-depth: 0

      - name: Install OpenCode CLI
        run: |
          curl -fsSL https://opencode.ai/install | bash
          echo "$HOME/.opencode/bin" >> $GITHUB_PATH

      - name: Collect context
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ISSUE_NUMBER: ${{ github.event.issue.number }}
        run: |
          # Build conversation history
          CONVERSATION=$(gh issue view "$ISSUE_NUMBER" --json body,comments --jq '...')
          
          # Create prompt with embedded context
          cat > .tmp/prompt.txt <<PROMPT_EOF
          You are an AI assistant...
          
          Context:
          Number: ${ISSUE_NUMBER}
          Conversation:
          ${CONVERSATION}
          
          [Detailed instructions...]
          PROMPT_EOF

      - name: Run OpenCode analysis
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_API_BASE: ${{ secrets.OPENAI_API_BASE }}
          OPENAI_MODEL: ${{ secrets.OPENAI_MODEL }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          opencode run "$(cat .tmp/prompt.txt)"

      - name: Verify response posted
        if: always()
        run: |
          # Check if AI actually posted a comment
          # If not, post a fallback message
          ...
```

### Key Features

**1. Smart Checkout Logic:**

- For issues: checkout `main`
- For PR comments: checkout the PR's branch (so AI can see changes)
- For external PRs: still checkout `main`

**2. User Filtering:**

```yaml
if: github.event.sender.login == 'lenaxia'
```

Only responds to specific user (adjust for your needs).

**3. Context Collection:**

```bash
CONVERSATION=$(gh issue view "$ISSUE_NUMBER" --json body,comments --jq '["=== ORIGINAL ISSUE ===", .body, "\n=== PREVIOUS COMMENTS ==="] + [.comments[] | "[\(.createdAt)] \(.author.login):\n\(.body)\n---"] | join("\n\n")')
```

Uses `gh` CLI with JSON output and jq to format conversation history.

**4. Fallback Verification:**

```yaml
- name: Verify response posted
  if: always()
  run: |
    # Get recent comments
    RECENT_BOT_COMMENTS=$(gh api ... | jq 'length')
    
    if [[ "$RECENT_BOT_COMMENTS" -eq 0 ]]; then
      # Post fallback message
      gh issue comment "$ISSUE_NUMBER" --body "I encountered an error..."
    fi
```

This ensures users get feedback even if AI fails to post.

### Prompt Structure

The prompt is organized into sections:

```markdown
You are an AI assistant for a [repository type] repository.

Context Information:
- Number: ${ISSUE_NUMBER}
- Event type: ${EVENT_NAME}

CONVERSATION HISTORY:
${CONVERSATION}

Repository Context:
[Describe your repo structure and common workflows]

CRITICAL RULES:
1. ALWAYS use github_add_issue_comment tool
2. NEVER output text - must call tool
...

Your Task:

Step 1: Analyze the request
[What to analyze]

Step 2: Determine appropriate action
[Options A-E: investigate, implement, clarify, etc.]

Step 3: Implementation details
[How to implement if needed]

Examples of responses:
[Show 2-3 examples of proper responses]

CRITICAL REMINDER:
[Mandatory actions checklist]
```

## Renovate PR Analyzer Workflow

This workflow analyzes Renovatebot PRs and can auto-merge safe ones.

### Key Features

**1. Dual Trigger Modes:**

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]
  workflow_dispatch:
    inputs:
      pr_number:
        description: 'PR number to analyze'
```

- Auto-triggered when Renovate opens a PR
- Manual trigger for specific PR or batch analysis

**2. Duplicate Detection:**

```yaml
# Check if PR was already analyzed
EXISTING_COMMENTS=$(gh pr view "$PR_NUMBER" --json comments --jq '.comments[] | select(.author.login == "github-actions" and (.body | startswith("## Renovate PR Analysis")))')

if [ -n "$EXISTING_COMMENTS" ]; then
  # Compare timestamps
  if [ "$PR_UPDATED_TS" -le "$COMMENT_BUFFER_TS" ]; then
    echo "✓ Already analyzed and no updates. Skipping."
    exit 0
  fi
fi
```

Skips re-analysis if PR hasn't changed since last analysis.

**3. Structured Analysis Output:**

The prompt requires a specific markdown format:

```markdown
## Renovate PR Analysis

### Update Summary
- Dependency: [name]
- Version: [old] → [new]
- Type: [patch/minor/major/digest]

### Release Changes
[What's new]

### Breaking Changes
[List or state "none"]

### Configuration Changes Required
[Detailed analysis]

### Migration Notes
[Any migration steps]

### Recommendation
- [Safe to merge / Needs manual review / Requires code changes]
- Explanation
```

**4. Action-Based Implementation:**

The AI must take specific actions:

```yaml
**If "Safe to merge":**
- Use github_merge_pull_request to merge
- Only if: no breaking changes, no new required params

**If "Requires code changes":**
- Create branch: config/renovate-pr-[PR_NUMBER]-changes
- Apply configuration changes
- Create PR with reference to original Renovate PR
- Comment on original PR: "Created PR #[NEW_PR] with config changes"

**If "Needs manual review":**
- Do NOT merge
- Do NOT create PR
- Only post analysis comment
```

**5. Exclusion List:**

```yaml
Special Exclusions:
1. Bitnami charts - Never upgrade (revoked)
2. MinIO - Deprecated open source
3. Authelia, Traefik - Require manual review
```

### Prompt Pattern

```markdown
You are an AI assistant that analyzes Renovatebot pull requests.

Process:

1. Get PRs to analyze:
   - Filter for "renovate[bot]" author
   - Check for existing analysis comments
   - Skip if already analyzed and unchanged

2. For each Renovate PR:
   a. Parse PR title (dependency, versions, type)
   b. Get files changed
   c. Identify upstream repository
   d. Fetch release information
   e. Analyze changes
   f. Check our configuration
   g. Determine needed changes

3. Create detailed analysis comment (format specified above)

4. Take action based on recommendation (merge/create PR/comment only)
```

## Failure Analysis Workflow

Analyzes failed GitHub Actions workflows and creates PRs with systematic fixes.

### Trigger Pattern

```yaml
on:
  workflow_run:
    workflows: ["e2e", "Kubeconform", "Flux Diff"]
    types: [completed]
  workflow_dispatch:
    inputs:
      run_id:
        required: false
```

Triggers automatically when specified workflows fail.

### Key Features

**1. Context Collection:**

```yaml
- name: Download workflow logs
  run: |
    gh api "repos/${{ github.repository }}/actions/runs/${RUN_ID}/logs" > .tmp/logs.zip
    unzip -q .tmp/logs.zip -d .tmp/logs/
    find .tmp/logs -type f -name "*.txt" -exec cat {} \; > .tmp/combined-logs.txt

- name: Get PR or commit context
  run: |
    PR_DATA=$(gh pr list --search "${HEAD_SHA}" --json number,title --limit 1)
    if [ "$(echo "$PR_DATA" | jq 'length')" -gt 0 ]; then
      gh pr diff "${PR_NUMBER}" > .tmp/pr-diff.txt
    fi
```

Downloads logs and gets PR/commit context.

**2. Root Cause Classification:**

The prompt classifies failures into categories:

- **A. Workflow Design Issues**: Flawed logic, permissions, ordering
- **B. Workflow Config Issues**: Invalid env vars, malformed YAML
- **C. Application Problems**: Code bugs, failing tests
- **D. GitOps Repository Issues**: Invalid manifests, Flux/Kustomization
- **E. Infrastructure Issues**: Resource limits, network, timeouts
- **F. Flaky Tests**: Intermittent, race conditions
- **G. Other**: Complex or manual investigation needed

**3. Systematic Fix Emphasis:**

```yaml
CRITICAL: Always prefer SYSTEMATIC fixes over PATCH fixes.

Systematic Fix Examples:
- Add validation checks to prevent errors
- Improve error messages
- Add pre-commit hooks
- Refactor workflow logic
- Add retry mechanisms

Patch Fix Examples (AVOID):
- Just fixing specific syntax error
- Commenting out failing tests
- Hardcoding values
```

**4. PR Creation Pattern:**

```yaml
Title: fix(failure-analysis): [category] resolve ${WORKFLOW_NAME} failure

Body:
## Automated Failure Analysis

### Failed Workflow
- Workflow: ${WORKFLOW_NAME}
- Run ID: ${RUN_ID}
- Branch: ${HEAD_BRANCH}
- SHA: ${HEAD_SHA}

### Root Cause
Category: [classification]
[Explanation]

### Systematic Fix
[Explain approach]

### Changes Made
[List files]

### Testing Performed
[Describe validation]

### Risk Assessment
Risk Level: [Low/Medium/High]
[Explain risks]

### Prevention
[How this prevents future issues]

Closes #605 (Automated Failure Analysis)
```

**5. Safety Mechanisms:**

```yaml
CRITICAL RULES:
- NEVER auto-merge PRs
- NEVER push directly to main/master
- ALWAYS create branch: fix/failure-analysis-${RUN_ID}
- ALWAYS assign PR to lenaxia
- For security-sensitive changes, mark as draft
- Add label: automated-fix
- If unsure, create issue instead of PR
```

## Prompt Engineering Best Practices

### 1. Explicit Tool Usage Requirements

**Do this:**

```markdown
CRITICAL RULES:
1. ALWAYS use the github_add_issue_comment tool to post a response
2. NEVER finish your analysis without calling github_add_issue_comment
3. Outputting text in your response is NOT the same as posting a comment
4. You MUST call the tool
```

**Don't do this:**

```markdown
Please post a response to the issue.
```

### 2. Step-by-Step Instructions

Break down tasks clearly:

```markdown
Your Task:

Step 1: Analyze the issue request
- Read and understand what lenaxia is asking for
- Determine if it's a question, implementation, clarification, etc.

Step 2: Determine appropriate action
Option A: Investigation/Research
Option B: Implement (create PR)
Option C: Ask for clarification
...

Step 3: If implementing (Option B), follow this process:
a. Determine implementation approach
b. Create a feature branch
c. Make your changes
d. Create a pull request
e. Notify with a comment
```

### 3. Provide Examples

Show concrete examples of what you expect:

```markdown
Example 1 - After implementing changes:
Call github_add_issue_comment with body:
"@lenaxia ✅ I've created a PR to deploy Jellyfin.

PR: #123 - feat(media): deploy jellyfin

Changes made:
- Added Jellyfin deployment
- Configured with defaults
- Ready for customization
"

Example 2 - When asking for clarification:
Call github_add_issue_comment with body:
"@lenaxia Thanks! Could you clarify:
1. Which namespace?
2. What values?
3. Any special config?
"
```

### 4. Visual Checklists

Use checkboxes for mandatory actions:

```markdown
CRITICAL REMINDER - MANDATORY ACTIONS BEFORE FINISHING:

1. CODE CHANGES CHECKLIST:
   ☐ Call github_create_branch to create a feature branch
   ☐ Use github_create_or_update_file to make changes
   ☐ Call github_create_pull_request to create the PR
   ☐ NEVER commit directly to main branch

2. COMMENT CHECKLIST:
   ☐ Call github_add_issue_comment to post your response
   ☐ Post findings / PR link / questions / explanation

3. CRITICAL ERRORS TO AVOID:
   ✗ Outputting text instead of calling github_add_issue_comment
   ✗ Making direct commits instead of creating a PR
   ✗ Creating files without creating a PR first
```

### 5. Repository Context

Provide context about your repository:

```markdown
Repository Context:
This is a Talos Linux Kubernetes cluster template managed with Flux.

Key directories:
- kubernetes/ - Contains cluster manifests
- .taskfiles/ - Contains Task scripts
- .github/ - Contains workflows and actions
- config.yaml - Main configuration

Common Workflows:

1. Deploy a new application
   - Create namespace.yaml
   - Create helmrelease.yaml
   - Create kustomization.yaml

2. Update configuration
   - Modify existing YAML files
   - Update Helm values

3. Create/modify workflows
   - Create .github/workflows/<name>.yml
```

### 6. Be Specific About Branch Naming

```yaml
# Specify exact branch format
Step 1: Call github_create_branch with branch name: feat/issue-${ISSUE_NUMBER}-<short-description>

# Example
Branch name: feat/issue-664-update-ai-workflows-guide
```

### 7. Handle Edge Cases

```yaml
# If issue body is very long, provide guidance
If the issue body is very long (>10,000 characters), provide a CONCISE summary response to avoid token limits.

# If AI is uncertain
If unsure about fix, create issue instead of PR

# Rate limiting
If 3+ failure-analysis PRs are already open, create an issue instead
```

## Common Patterns

### Pattern 1: Issue/PR Comment Handler

```yaml
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

jobs:
  handler:
    if: |
      github.event.sender.login == 'your-user' &&
      (github.event_name == 'issue_comment' || startsWith(github.event.comment.body, '/ai'))
    
    steps:
      - name: Determine checkout ref
        if: github.event.issue.pull_request != null
        run: |
          PR_NUMBER="${{ github.event.issue.number }}"
          PR_BRANCH=$(gh pr view "$PR_NUMBER" --json headRefName --jq '.headRefName')
          echo "checkout-ref=${PR_BRANCH}" >> $GITHUB_OUTPUT
      
      - uses: actions/checkout@v6
        with:
          ref: ${{ steps.determine-ref.outputs.checkout-ref || 'main' }}
      
      - name: Collect context
        run: |
          # Build context with gh CLI
          ...
      
      - name: Run OpenCode
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_API_BASE: ${{ secrets.OPENAI_API_BASE }}
        run: |
          opencode run "$(cat .tmp/prompt.txt)"
```

### Pattern 2: Workflow Failure Analyzer

```yaml
on:
  workflow_run:
    workflows: ["your-workflow"]
    types: [completed]

jobs:
  analyze:
    if: github.event.workflow_run.conclusion == 'failure'
    steps:
      - name: Download logs
        run: |
          RUN_ID="${{ github.event.workflow_run.id }}"
          gh api "repos/${{ github.repository }}/actions/runs/${RUN_ID}/logs" > logs.zip
          unzip logs.zip
      
      - name: Analyze
        run: |
          opencode run "Analyze these workflow logs and create a PR with fixes..."
```

### Pattern 3: Bot PR Analyzer

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  analyze-bot-pr:
    if: github.event.pull_request.user.login == 'renovate[bot]'
    steps:
      - name: Check for existing analysis
        run: |
          # Check if PR already has analysis comment
          # Compare timestamps to see if PR was updated
          ...
      
      - name: Analyze
        run: |
          opencode run "Analyze this Renovate PR and provide recommendations..."
```

### Pattern 4: Scheduled Maintenance

```yaml
on:
  schedule:
    - cron: "0 */12 * * *"
  workflow_dispatch:

jobs:
  maintenance:
    steps:
      - name: Get recent changes
        run: |
          CHANGES=$(git log --since="12 hours ago")
          opencode run "Review these changes: ${CHANGES}"
```

## Key Learnings & Gotchas

### 1. Self-Hosted vs SaaS

**This repo uses self-hosted:**
- `OPENAI_API_BASE` points to internal endpoint
- No dependency on external SaaS
- Model: `vllm-local/default` or similar

**Benefits:**
- Cost control
- Privacy
- Custom models
- No rate limits

### 2. Tool Usage is NOT Automatic

**Gotcha:** Even if you grant permissions, AI won't use tools unless explicitly told to.

**Solution:**
```yaml
# In prompt, be very explicit:
CRITICAL: You MUST call github_add_issue_comment.
Do NOT just output text.
Outputting text ≠ calling the tool.
```

### 3. AI Might Not Post Comments

**Gotcha:** AI can complete analysis but fail to post comment (e.g., tool call error).

**Solution:**
```yaml
- name: Verify response posted
  if: always()
  run: |
    # Check for recent bot comment
    RECENT_BOT_COMMENTS=$(gh api ... | jq 'length')
    
    if [[ "$RECENT_BOT_COMMENTS" -eq 0 ]]; then
      # Post fallback
      gh issue comment "$ISSUE_NUMBER" --body "I encountered an error..."
    fi
```

### 4. Branch Checkout is Tricky

**Gotcha:** For PR comments, you need to checkout the PR's branch, not main, to see the changes.

**Solution:**
```yaml
- name: Determine checkout ref
  if: github.event.issue.pull_request != null
  run: |
    PR_NUMBER="${{ github.event.issue.number }}"
    PR_BRANCH=$(gh pr view "$PR_NUMBER" --json headRefName --jq '.headRefName')
    echo "checkout-ref=${PR_BRANCH}" >> $GITHUB_OUTPUT

- uses: actions/checkout@v6
  with:
    ref: ${{ steps.determine-ref.outputs.checkout-ref || 'main' }}
```

### 5. Prompt Size Limits

**Gotcha:** Large prompts can hit token limits, especially with full git diffs.

**Solution:**
```yaml
# Truncate large content
if [[ ${#ISSUE_BODY} -gt 10000 ]]; then
  ISSUE_BODY="${ISSUE_BODY:0:10000}"
fi

# Or include guidance in prompt
If the issue body is very long (>10,000 characters), provide a CONCISE summary.
```

### 6. Heredoc Quoting

**Gotcha:** Using heredocs in YAML can cause issues with variable expansion.

**Solution:**
```yaml
# Use quoted heredoc to prevent variable expansion
cat > .tmp/prompt.txt <<'PROMPT_EOF'
You are an AI assistant...
Variables like ${VAR} won't be expanded here.
PROMPT_EOF

# Then substitute later
envsubst < .tmp/prompt.txt > .tmp/final-prompt.txt
```

### 7. Duplicate Detection

**Gotcha:** Without duplicate detection, workflows might repeat work on every re-run.

**Solution:**
```yaml
# Check for existing comments
EXISTING=$(gh pr view "$PR" --json comments --jq '.comments[] | select(.body | startswith("## Analysis"))')

if [ -n "$EXISTING" ]; then
  # Compare timestamps
  if [ "$PR_UPDATED" -le "$COMMENT_TIME" ]; then
    exit 0  # Skip
  fi
fi
```

### 8. External PRs

**Gotcha:** PRs from forks can't be checked out by ref in the same way.

**Solution:**
```yaml
# Check if PR is from external repo
REPO_NAME=$(gh pr view "$PR" --json headRepository --jq '.headRepository.nameWithOwner')

if [[ "$REPO_NAME" != "${{ github.repository }}" ]]; then
  echo "checkout-ref=main" >> $GITHUB_OUTPUT
fi
```

### 9. Workflow Permissions

**Gotcha:** Need to explicitly grant permissions for AI to take actions.

**Solution:**
```yaml
permissions:
  contents: write      # For creating branches/files
  issues: write        # For commenting on issues
  pull-requests: write # For commenting on PRs, merging
  actions: read        # For reading workflow logs
```

### 10. Artifact Retention

**Gotcha:** Generated files are lost after workflow runs unless saved.

**Solution:**
```yaml
- name: Upload artifacts
  if: always()
  uses: actions/upload-artifact@v6
  with:
    name: analysis-${{ github.run_id }}
    path: .tmp/*.txt
    retention-days: 30
```

## Troubleshooting

### Problem: AI not posting comments

**Symptoms:** Workflow completes successfully, but no comment appears on issue/PR.

**Solutions:**
1. Check if tool usage is explicitly required in prompt
2. Verify permissions in workflow
3. Check GitHub Actions logs for tool call errors
4. Implement fallback verification step (see Pattern 1)

### Problem: AI not seeing PR changes

**Symptoms:** AI says "no files changed" when PR has changes.

**Solutions:**
1. Ensure you're checking out the PR's branch (not main)
2. Use `fetch-depth: 0` to get full history
3. Verify `gh pr diff` is fetching correctly

### Problem: Prompt too large

**Symptoms:** Context truncated, AI missing information.

**Solutions:**
1. Implement truncation for large content
2. Focus on most relevant context only
3. Use shorter, more targeted prompts
4. Ask AI to request specific information as needed

### Problem: Workflow re-running unnecessarily

**Symptoms:** Same analysis posted multiple times.

**Solutions:**
1. Implement duplicate detection (check existing comments)
2. Compare timestamps to see if content changed
3. Skip if no new changes since last analysis

### Problem: Wrong branch checked out

**Symptoms:** AI can't see new files in PR.

**Solutions:**
1. Implement smart checkout logic (PR branch vs main)
2. Handle external PRs (forks) specially
3. Verify checkout ref in workflow logs

### Problem: No fallback for errors

**Symptoms:** Silent failures, users get no feedback.

**Solutions:**
1. Always include `if: always()` verification step
2. Post fallback message if AI doesn't respond
3. Include workflow run URL in fallback for debugging

## Getting Started Checklist

### For Your Repository:

1. [ ] Set up secrets (OPENAI_API_KEY, OPENAI_API_BASE, OPENAI_MODEL)
2. [ ] Create `.github/workflows/` directory structure
3. [ ] Start with simple Issue Responder workflow
4. [ ] Test manually with `/ai` command or new issue
5. [ ] Add verification step to ensure AI posts comments
6. [ ] Review workflow logs and artifacts
7. [ ] Iterate on prompt based on results
8. [ ] Add more workflows as needed (Renovate analyzer, etc.)

### For Prompts:

1. [ ] Be explicit about tool usage requirements
2. [ ] Provide step-by-step instructions
3. [ ] Include concrete examples
4. [ ] Add visual checklists
5. [ ] Provide repository context
6. [ ] Handle edge cases
7. [ ] Specify exact branch naming conventions
8. [ ] Include safety mechanisms

### For Workflows:

1. [ ] Use proper permissions
2. [ ] Implement smart checkout logic
3. [ ] Add context collection with `gh` CLI
4. [ ] Include verification/fallback step
5. [ ] Upload artifacts for debugging
6. [ ] Implement duplicate detection where applicable
7. [ ] Handle external PRs/forks
8. [ ] Test with different event types

## Resources

- OpenCode CLI: https://opencode.ai
- GitHub Actions Documentation: https://docs.github.com/en/actions
- GitHub CLI (gh): https://cli.github.com
- OpenAI API: https://platform.openai.com/docs/api-reference
