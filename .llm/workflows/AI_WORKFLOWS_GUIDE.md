# Comprehensive Guide: Replicating AI-Powered Workflows

This guide explains how to replicate the sophisticated AI-powered workflows used in the opencode repository. It covers slash commands, issue triage, PR review, documentation updates, testing, publishing, and statistics collection.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites & Setup](#prerequisites--setup)
3. [Slash Command Workflows](#slash-command-workflows)
4. [Issue Triage Automation](#issue-triage-automation)
5. [PR Review Automation](#pr-review-automation)
6. [Documentation Updates](#documentation-updates)
7. [Testing with AI](#testing-with-ai)
8. [Publishing Workflows](#publishing-workflows)
9. [Statistics Collection](#statistics-collection)
10. [Language Recommendations](#language-recommendations)
11. [Best Practices](#best-practices)

## Architecture Overview

The opencode AI workflows follow a consistent pattern:

```
GitHub Event -> GitHub Action -> opencode AI -> Results/Actions
```

Key components:

- **GitHub Actions**: Trigger workflows on events (issues, PRs, comments, schedules)
- **opencode CLI/SDK**: AI analysis engine with specialized agents
- **Specialized Agents**: Task-specific AI configurations (triage, docs, review, etc.)
- **Permission Control**: Fine-grained tool access restrictions
- **Model Selection**: Appropriate AI models for different task complexities

## Prerequisites & Setup

### 1. Required Accounts & Tokens

```bash
# GitHub Secrets needed:
OPENCODE_API_KEY=your_opencode_api_key
GITHUB_TOKEN=${{ secrets.GITHUB_TOKEN }}  # Auto-provided
ANTHROPIC_API_KEY=optional_for_claude_models
DISCORD_WEBHOOK_URL=for_notifications
POSTHOG_KEY=for_analytics
```

### 2. Repository Structure

```
.github/
├── workflows/
│   ├── opencode.yml          # Main slash command handler
│   ├── triage.yml           # Issue triage
│   ├── review.yml           # PR review
│   ├── duplicate-issues.yml # Duplicate detection
│   ├── docs-update.yml      # Documentation updates
│   ├── test.yml            # Testing workflows
│   └── publish.yml         # Publishing
├── actions/
│   └── setup-bun/          # Shared setup action
└── ISSUE_TEMPLATE/

script/
├── changelog.ts           # Changelog generation
├── duplicate-pr.ts        # PR duplicate analysis
├── stats.ts              # Statistics collection
├── sync-zed.ts           # Editor sync
└── publish-*.ts          # Publishing scripts
```

### 3. Base Setup Action

Create `.github/actions/setup-bun/action.yml`:

```yaml
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
      run: bun install --frozen-lockfile
```

## Slash Command Workflows

### 1. Main Slash Command Handler

Create `.github/workflows/opencode.yml`:

```yaml
name: opencode

on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

jobs:
  opencode:
    if: |
      contains(github.event.comment.body, ' /oc') ||
      startsWith(github.event.comment.body, '/oc') ||
      contains(github.event.comment.body, ' /opencode') ||
      startsWith(github.event.comment.body, '/opencode')
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
      pull-requests: read
      issues: read
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      
      - uses: ./.github/actions/setup-bun
      
      - name: Run opencode
        uses: anomalyco/opencode/github@latest
        env:
          OPENCODE_API_KEY: ${{ secrets.OPENCODE_API_KEY }}
          OPENCODE_PERMISSION: '{"bash": "deny"}'
        with:
          model: opencode/claude-opus-4-5
```

### 2. Custom Command Handlers

For specific commands like `/review`:

```yaml
name: Review Command

on:
  issue_comment:
    types: [created]

jobs:
  review:
    if: |
      github.event.issue.pull_request &&
      startsWith(github.event.comment.body, '/review') &&
      contains(fromJson('["OWNER","MEMBER"]'), github.event.comment.author_association)
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      
      - uses: ./.github/actions/setup-bun
      
      - name: Install opencode
        run: curl -fsSL https://opencode.ai/install | bash
      
      - name: Run review
        env:
          OPENCODE_API_KEY: ${{ secrets.OPENCODE_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENCODE_PERMISSION: |
            {
              "bash": {
                "*": "deny",
                "gh*": "allow",
                "gh pr review*": "deny"
              }
            }
        run: |
          opencode run -m anthropic/claude-opus-4-5 "Review this PR: ${{ github.event.issue.number }}"
```

## Issue Triage Automation

### 1. Basic Triage Workflow

Create `.github/workflows/triage.yml`:

```yaml
name: Issue Triage

on:
  issues:
    types: [opened]

jobs:
  triage:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 1
      
      - name: Setup Bun
        uses: ./.github/actions/setup-bun
      
      - name: Install opencode
        run: curl -fsSL https://opencode.ai/install | bash
      
      - name: Triage issue
        env:
          OPENCODE_API_KEY: ${{ secrets.OPENCODE_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ISSUE_NUMBER: ${{ github.event.issue.number }}
          ISSUE_TITLE: ${{ github.event.issue.title }}
          ISSUE_BODY: ${{ github.event.issue.body }}
        run: |
          opencode run --agent triage "The following issue was just opened, triage it:

          Title: $ISSUE_TITLE

          $ISSUE_BODY"
```

### 2. Enhanced Triage with Labels

Create `script/triage.ts` for more sophisticated triage:

```typescript
#!/usr/bin/env bun

import { createOpencode } from "@opencode-ai/sdk"

interface Issue {
  number: number
  title: string
  body: string
  labels: string[]
}

async function triageIssue(issue: Issue) {
  const opencode = await createOpencode({ port: 0 })
  
  try {
    const session = await opencode.client.session.create()
    const result = await opencode.client.session.prompt({
      path: { id: session.data!.id },
      body: {
        agent: "triage",
        model: { providerID: "opencode", modelID: "claude-sonnet-4-5" },
        parts: [
          {
            type: "text",
            text: `Triage this issue and suggest:
1. Priority (P0, P1, P2, P3)
2. Category (bug, feature, question, documentation)
3. Relevant labels
4. Team assignment if applicable

Issue #${issue.number}: ${issue.title}

${issue.body}`
          }
        ]
      }
    })
    
    return result.data?.parts?.find(p => p.type === "text")?.text || ""
  } finally {
    opencode.server.close()
  }
}

// Export for use in workflows
export { triageIssue }
```

## PR Review Automation

### 1. Style Guide Enforcement

Create `.github/workflows/review.yml`:

```yaml
name: Guidelines Check

on:
  issue_comment:
    types: [created]

jobs:
  check-guidelines:
    if: |
      github.event.issue.pull_request &&
      startsWith(github.event.comment.body, '/review') &&
      contains(fromJson('["OWNER","MEMBER"]'), github.event.comment.author_association)
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: Get PR details
        id: pr-details
        run: |
          gh api /repos/${{ github.repository }}/pulls/${{ github.event.issue.number }} > pr_data.json
          echo "title=$(jq -r .title pr_data.json)" >> $GITHUB_OUTPUT
          echo "sha=$(jq -r .head.sha pr_data.json)" >> $GITHUB_OUTPUT
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Check PR guidelines compliance
        env:
          OPENCODE_API_KEY: ${{ secrets.OPENCODE_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENCODE_PERMISSION: |
            {
              "bash": {
                "*": "deny",
                "gh*": "allow",
                "gh pr review*": "deny"
              }
            }
          PR_TITLE: ${{ steps.pr-details.outputs.title }}
        run: |
          PR_BODY=$(jq -r .body pr_data.json)
          opencode run -m anthropic/claude-opus-4-5 "Review PR #${{ github.event.issue.number }}: '${PR_TITLE}'
          
          <pr-description>
          ${PR_BODY}
          </pr-description>
          
          Check code changes against our style guide. Look for:
          1. Code style violations
          2. Potential bugs
          3. Security issues
          4. Performance concerns
          
          Create GitHub comments for significant issues. Use exact line numbers."
```

### 2. PR Review Script

Create `script/review.ts` for programmatic reviews:

```typescript
#!/usr/bin/env bun

import { createOpencode } from "@opencode-ai/sdk"
import { $ } from "bun"

interface PRReviewConfig {
  prNumber: number
  repo: string
  styleGuide?: string
  focusAreas?: string[]
}

async function reviewPR(config: PRReviewConfig) {
  const opencode = await createOpencode({ port: 0 })
  
  try {
    // Get PR details
    const prData = await $`gh pr view ${config.prNumber} --repo ${config.repo} --json number,title,body,files,additions,deletions`.json()
    
    // Get diff
    const diff = await $`gh pr diff ${config.prNumber} --repo ${config.repo}`.text()
    
    const session = await opencode.client.session.create()
    const result = await opencode.client.session.prompt({
      path: { id: session.data!.id },
      body: {
        agent: "review",
        model: { providerID: "opencode", modelID: "claude-opus-4-5" },
        parts: [
          {
            type: "text",
            text: `Review PR #${prData.number}: ${prData.title}
            
            Description: ${prData.body}
            
            Files changed: ${prData.files.map(f => f.path).join(', ')}
            Additions: ${prData.additions}, Deletions: ${prData.deletions}
            
            ${config.styleGuide ? `Style Guide:\n${config.styleGuide}\n` : ''}
            
            Diff:
            ${diff}
            
            Provide specific, actionable feedback. Focus on:
            ${config.focusAreas?.join(', ') || 'code quality, bugs, security, performance'}`
          }
        ]
      }
    })
    
    return result.data?.parts?.find(p => p.type === "text")?.text || ""
  } finally {
    opencode.server.close()
  }
}

export { reviewPR }
```

## Documentation Updates

### 1. Automated Documentation Updates

Create `.github/workflows/docs-update.yml`:

```yaml
name: Docs Update

on:
  schedule:
    - cron: "0 */12 * * *"  # Every 12 hours
  workflow_dispatch:

env:
  LOOKBACK_HOURS: 4

jobs:
  update-docs:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Setup Bun
        uses: ./.github/actions/setup-bun
      
      - name: Get recent commits
        id: commits
        run: |
          COMMITS=$(git log --since="${{ env.LOOKBACK_HOURS }} hours ago" --pretty=format:"- %h %s" 2>/dev/null || echo "")
          if [ -z "$COMMITS" ]; then
            echo "has_commits=false" >> $GITHUB_OUTPUT
          else
            echo "has_commits=true" >> $GITHUB_OUTPUT
            {
              echo "list<<EOF"
              echo "$COMMITS"
              echo "EOF"
            } >> $GITHUB_OUTPUT
          fi
      
      - name: Update documentation
        if: steps.commits.outputs.has_commits == 'true'
        env:
          OPENCODE_API_KEY: ${{ secrets.OPENCODE_API_KEY }}
        run: |
          opencode run -m opencode/gpt-5.2 --agent docs "
          Review these commits from last ${{ env.LOOKBACK_HOURS }} hours:
          
          ${{ steps.commits.outputs.list }}
          
          Identify undocumented features and update documentation accordingly.
          Focus on user-facing changes only."
```

### 2. Documentation Script

Create `script/docs-update.ts`:

```typescript
#!/usr/bin/env bun

import { createOpencode } from "@opencode-ai/sdk"
import { $ } from "bun"
import fs from "fs"

interface DocUpdateConfig {
  docsPath: string
  lookbackHours: number
}

async function updateDocumentation(config: DocUpdateConfig) {
  const opencode = await createOpencode({ port: 0 })
  
  try {
    // Get recent commits
    const commits = await $`git log --since="${config.lookbackHours} hours ago" --pretty=format:"%H %s"`.text()
    
    if (!commits.trim()) {
      console.log("No commits in specified timeframe")
      return
    }
    
    const session = await opencode.client.session.create()
    const result = await opencode.client.session.prompt({
      path: { id: session.data!.id },
      body: {
        agent: "docs",
        model: { providerID: "opencode", modelID: "gpt-5.2" },
        parts: [
          {
            type: "text",
            text: `Analyze these commits for documentation needs:
            
            ${commits}
            
            Documentation directory: ${config.docsPath}
            
            Update documentation for any new features, API changes, or significant modifications.
            Focus on user-facing changes only.`
          }
        ]
      }
    })
    
    const analysis = result.data?.parts?.find(p => p.type === "text")?.text || ""
    console.log("Documentation analysis:", analysis)
    
  } finally {
    opencode.server.close()
  }
}

export { updateDocumentation }
```

## Testing with AI

### 1. AI-Enhanced Testing Workflow

Create `.github/workflows/test.yml`:

```yaml
name: Test

on:
  push:
    branches: [main, dev]
  pull_request:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      
      - name: Setup Bun
        uses: ./.github/actions/setup-bun
      
      - name: Run tests with AI analysis
        env:
          OPENCODE_API_KEY: ${{ secrets.OPENCODE_API_KEY }}
          OPENCODE_PERMISSION: |
            {
              "bash": {
                "*": "deny",
                "npm*": "allow",
                "bun*": "allow"
              }
            }
        run: |
          # Run standard tests
          bun test
          
          # AI analysis of test results
          if [ -f "test-results.json" ]; then
            opencode run -m opencode/claude-haiku-4-5 "
            Analyze these test results and identify:
            1. Flaky tests
            2. Slow tests
            3. Test coverage gaps
            4. Suggestions for improvement
            
            Test results:
            $(cat test-results.json | head -1000)
            "
          fi
```

### 2. Test Generation Script

Create `script/generate-tests.ts`:

```typescript
#!/usr/bin/env bun

import { createOpencode } from "@opencode-ai/sdk"
import fs from "fs"

interface TestGenerationConfig {
  sourceFile: string
  testFile: string
  framework: 'jest' | 'vitest' | 'mocha' | 'bun'
}

async function generateTests(config: TestGenerationConfig) {
  const opencode = await createOpencode({ port: 0 })
  
  try {
    const sourceCode = await fs.promises.readFile(config.sourceFile, 'utf-8')
    const existingTests = fs.existsSync(config.testFile) 
      ? await fs.promises.readFile(config.testFile, 'utf-8')
      : ''
    
    const session = await opencode.client.session.create()
    const result = await opencode.client.session.prompt({
      path: { id: session.data!.id },
      body: {
        agent: "test",
        model: { providerID: "opencode", modelID: "claude-sonnet-4-5" },
        parts: [
          {
            type: "text",
            text: `Generate comprehensive tests for this ${config.framework} test file.
            
            Source code (${config.sourceFile}):
            ${sourceCode}
            
            ${existingTests ? `Existing tests (${config.testFile}):\n${existingTests}\n\nUpdate and expand these tests.` : 'Create new tests.'}
            
            Requirements:
            1. Cover all public functions/methods
            2. Include edge cases
            3. Follow ${config.framework} best practices
            4. Add meaningful assertions
            5. Include setup/teardown if needed
            
            Output only the complete test file content.`
          }
        ]
      }
    })
    
    const tests = result.data?.parts?.find(p => p.type === "text")?.text || ""
    
    if (tests) {
      await fs.promises.writeFile(config.testFile, tests)
      console.log(`Generated tests for ${config.sourceFile}`)
    }
    
  } finally {
    opencode.server.close()
  }
}

export { generateTests }
```

## Publishing Workflows

### 1. Automated Publishing

Create `.github/workflows/publish.yml`:

```yaml
name: Publish

on:
  release:
    types: [published]
  workflow_dispatch:

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Setup Bun
        uses: ./.github/actions/setup-bun
      
      - name: Generate changelog
        id: changelog
        env:
          OPENCODE_API_KEY: ${{ secrets.OPENCODE_API_KEY }}
        run: |
          PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
          CURRENT_TAG=${GITHUB_REF#refs/tags/}
          
          bun script/changelog.ts --from $PREV_TAG --to $CURRENT_TAG > changelog.md
          echo "changelog=$(cat changelog.md)" >> $GITHUB_OUTPUT
      
      - name: Update release notes
        uses: softprops/action-gh-release@v1
        with:
          body_path: changelog.md
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Publish to package registries
        run: |
          # Publish to npm
          npm publish --access public
          
          # Publish to other registries as needed
          # bunx jsr publish
      
      - name: Notify channels
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: |
          VERSION=${GITHUB_REF#refs/tags/}
          
          # Discord notification
          if [ -n "$DISCORD_WEBHOOK_URL" ]; then
            curl -H "Content-Type: application/json" \
                 -X POST \
                 -d '{"content": "🚀 Version '"$VERSION"' published!'"' \
                 "$DISCORD_WEBHOOK_URL"
          fi
```

### 2. Publishing Scripts

Create `script/publish-start.ts`:

```typescript
#!/usr/bin/env bun

import { createOpencode } from "@opencode-ai/sdk"
import { $ } from "bun"

async function prePublishCheck() {
  const opencode = await createOpencode({ port: 0 })
  
  try {
    // Check for uncommitted changes
    const status = await $`git status --porcelain`.text()
    if (status.trim()) {
      throw new Error("There are uncommitted changes")
    }
    
    // Run tests
    await $`bun test`
    
    // AI review of release readiness
    const session = await opencode.client.session.create()
    const result = await opencode.client.session.prompt({
      path: { id: session.data!.id },
      body: {
        model: { providerID: "opencode", modelID: "claude-sonnet-4-5" },
        parts: [
          {
            type: "text",
            text: `Review this repository for release readiness.
            
            Check:
            1. All tests passing
            2. No known critical bugs
            3. Documentation up to date
            4. Version numbers updated
            5. Changelog prepared
            
            Provide release readiness assessment.`
          }
        ]
      }
    })
    
    const assessment = result.data?.parts?.find(p => p.type === "text")?.text || ""
    console.log("Release readiness assessment:", assessment)
    
  } finally {
    opencode.server.close()
  }
}

prePublishCheck().catch(console.error)
```

## Statistics Collection

### 1. Stats Collection Workflow

Create `.github/workflows/stats.yml`:

```yaml
name: Stats Collection

on:
  schedule:
    - cron: "0 0 * * *"  # Daily at midnight
  workflow_dispatch:

jobs:
  collect-stats:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      
      - name: Setup Bun
        uses: ./.github/actions/setup-bun
      
      - name: Collect and analyze statistics
        env:
          POSTHOG_KEY: ${{ secrets.POSTHOG_KEY }}
          OPENCODE_API_KEY: ${{ secrets.OPENCODE_API_KEY }}
        run: bun script/stats.ts
```

### 2. Statistics Script

Create `script/stats.ts`:

```typescript
#!/usr/bin/env bun

interface Stats {
  date: string
  downloads: {
    npm?: number
    github?: number
  }
  activity: {
    issues: number
    prs: number
    commits: number
  }
}

async function collectStats(): Promise<Stats> {
  const date = new Date().toISOString().split('T')[0]
  
  // Collect GitHub stats
  const headers = {
    'Authorization': `Bearer ${process.env.GITHUB_TOKEN}`,
    'Accept': 'application/vnd.github.v3+json'
  }
  
  const [issues, prs, commits] = await Promise.all([
    fetch('https://api.github.com/repos/owner/repo/issues?state=all&per_page=1', { headers })
      .then(r => r.headers.get('Link')?.match(/page=(\d+)>; rel="last"/)?.[1] || '0'),
    
    fetch('https://api.github.com/repos/owner/repo/pulls?state=all&per_page=1', { headers })
      .then(r => r.headers.get('Link')?.match(/page=(\d+)>; rel="last"/)?.[1] || '0'),
    
    fetch('https://api.github.com/repos/owner/repo/commits?per_page=1', { headers })
      .then(r => r.headers.get('Link')?.match(/page=(\d+)>; rel="last"/)?.[1] || '0')
  ])
  
  return {
    date,
    downloads: { npm: 0, github: 0 },
    activity: {
      issues: parseInt(issues),
      prs: parseInt(prs),
      commits: parseInt(commits)
    }
  }
}

async function sendToAnalytics(stats: Stats) {
  if (!process.env.POSTHOG_KEY) return
  
  await fetch('https://us.i.posthog.com/capture/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: process.env.POSTHOG_KEY,
      event: 'project_stats',
      properties: stats,
      distinct_id: 'stats_collector'
    })
  })
}

// Run if called directly
if (import.meta.main) {
  const stats = await collectStats()
  console.log(JSON.stringify(stats, null, 2))
  await sendToAnalytics(stats)
}

export { collectStats }
```

## Language Recommendations

### Is TypeScript the Best Choice?

**Yes, TypeScript is ideal for these workflows because:**

1. **Type Safety**: Catches errors at compile time
2. **Rich Ecosystem**: Excellent tooling (Bun, esbuild, tsc)
3. **AI Friendliness**: Clear types help AI understand code structure
4. **Modern Features**: Async/await, modules, decorators
5. **Cross-Platform**: Runs anywhere Node.js/Bun runs

### Alternative Languages

| Language | Pros | Cons | Best For |
|----------|------|------|----------|
| **TypeScript** | Type safety, great tooling, AI-friendly | Build step required | All workflows |
| **Python** | Simple syntax, rich AI libraries | Slower, less type safety | Data analysis, ML workflows |
| **Go** | Fast, compiled, simple deployment | Less expressive, smaller ecosystem | High-performance scripts |
| **Bash** | No dependencies, runs everywhere | Error-prone, limited features | Simple glue scripts |

### Recommended Stack

```json
{
  "runtime": "Bun",
  "language": "TypeScript",
  "packageManager": "bun",
  "testing": "bun:test",
  "linting": "biome",
  "formatting": "biome",
  "bundling": "bun build"
}
```

### Package.json Template

```json
{
  "name": "your-project",
  "type": "module",
  "scripts": {
    "dev": "bun run --watch src/index.ts",
    "build": "bun build ./src/index.ts --outdir ./dist --target node",
    "test": "bun test",
    "lint": "biome check .",
    "format": "biome format --write .",
    "changelog": "bun script/changelog.ts",
    "stats": "bun script/stats.ts"
  },
  "dependencies": {
    "@opencode-ai/sdk": "^1.0.0"
  },
  "devDependencies": {
    "@types/bun": "latest",
    "biome": "latest",
    "typescript": "latest"
  }
}
```

## Best Practices

### 1. Security

```yaml
# Always:
- Use secrets for API keys
- Restrict permissions with OPENCODE_PERMISSION
- Validate AI outputs before acting
- Use read-only tokens where possible
- Audit AI actions regularly

# Never:
- Expose secrets in logs
- Grant unrestricted bash access
- Trust AI outputs without validation
- Run on untrusted code without sandboxing
```

### 2. Performance

```typescript
// Batch AI requests
const BATCH_SIZE = 10
for (let i = 0; i < items.length; i += BATCH_SIZE) {
  const batch = items.slice(i, i + BATCH_SIZE)
  await Promise.all(batch.map(processItem))
}

// Use appropriate models
const modelMap = {
  'simple': 'opencode/claude-haiku-4-5',
  'general': 'opencode/claude-sonnet-4-5', 
  'complex': 'opencode/claude-opus-4-5',
  'creative': 'opencode/gpt-5.2'
}
```

### 3. Reliability

```typescript
// Add retries with exponential backoff
async function withRetry(fn: () => Promise, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn()
    } catch (error) {
      if (i === maxRetries - 1) throw error
      await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, i)))
    }
  }
}

// Validate outputs
function validateAIResponse(response: string): boolean {
  const blacklist = ['rm -rf', 'DROP DATABASE', 'eval(']
  return !blacklist.some(pattern => response.includes(pattern))
}
```

## Getting Started

1. Install opencode CLI: `curl -fsSL https://opencode.ai/install | bash`
2. Create your GitHub workflows in `.github/workflows/`
3. Add required secrets to your repository settings
4. Test workflows manually using `workflow_dispatch`
5. Monitor AI usage and costs
6. Iterate and improve prompts based on results

## Resources

- opencode Documentation: https://opencode.ai/docs
- opencode GitHub: https://github.com/anomalyco/opencode
- @opencode-ai/sdk: https://npmjs.com/package/@opencode-ai/sdk
