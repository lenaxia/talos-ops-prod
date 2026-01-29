#!/usr/bin/env bash
set -euo pipefail

# Validation script for failure-analysis workflow
# Tests all requirements from the design proposal

WORKFLOW_FILE=".github/workflows/failure-analysis.yml"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================="
echo "Failure Analysis Workflow Validator"
echo "=================================="
echo ""

# Check if yq is installed
if ! command -v yq &> /dev/null; then
    echo -e "${RED}✗ yq is not installed. Please install yq to run this validation.${NC}"
    exit 1
fi

ERRORS=0
WARNINGS=0

# Function to print test result
pass() {
    echo -e "${GREEN}✓${NC} $1"
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((ERRORS++))
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

# Check workflow file exists
if [ ! -f "$WORKFLOW_FILE" ]; then
    fail "Workflow file not found: $WORKFLOW_FILE"
    exit 1
fi
pass "Workflow file exists"

echo ""
echo "Testing Workflow Triggers..."
echo "----------------------------"

# Test 1: Workflow triggers on correct workflows
TRIGGERS=$(yq '.on.workflow_run.workflows[]' "$WORKFLOW_FILE" 2>/dev/null || echo "")
if echo "$TRIGGERS" | grep -q "e2e"; then
    pass "Triggers on 'e2e' workflow"
else
    fail "Missing trigger for 'e2e' workflow"
fi

if echo "$TRIGGERS" | grep -q "Kubeconform"; then
    pass "Triggers on 'Kubeconform' workflow"
else
    fail "Missing trigger for 'Kubeconform' workflow"
fi

if echo "$TRIGGERS" | grep -q "Flux Diff"; then
    pass "Triggers on 'Flux Diff' workflow"
else
    fail "Missing trigger for 'Flux Diff' workflow"
fi

# Test 2: Workflow triggers on 'completed' type
TYPES=$(yq '.on.workflow_run.types[]' "$WORKFLOW_FILE" 2>/dev/null || echo "")
if echo "$TYPES" | grep -q "completed"; then
    pass "Triggers on 'completed' event type"
else
    fail "Should trigger on 'completed' event type"
fi

# Test 3: Manual dispatch available
if yq -e '.on.workflow_dispatch' "$WORKFLOW_FILE" &> /dev/null; then
    pass "Manual dispatch trigger configured"
else
    fail "Missing workflow_dispatch trigger"
fi

# Test 4: Manual dispatch has run_id input
if yq -e '.on.workflow_dispatch.inputs.run_id' "$WORKFLOW_FILE" &> /dev/null; then
    pass "Manual dispatch has 'run_id' input"
else
    fail "Missing 'run_id' input for manual dispatch"
fi

echo ""
echo "Testing Permissions..."
echo "----------------------"

# Test 5: Required permissions
PERMS=$(yq '.jobs.analyze-failure.permissions' "$WORKFLOW_FILE" 2>/dev/null || echo "")

if echo "$PERMS" | grep -q "contents.*write"; then
    pass "Has 'contents: write' permission"
else
    fail "Missing 'contents: write' permission"
fi

if echo "$PERMS" | grep -q "issues.*write"; then
    pass "Has 'issues: write' permission"
else
    fail "Missing 'issues: write' permission"
fi

if echo "$PERMS" | grep -q "pull-requests.*write"; then
    pass "Has 'pull-requests: write' permission"
else
    fail "Missing 'pull-requests: write' permission"
fi

if echo "$PERMS" | grep -q "actions.*read"; then
    pass "Has 'actions: read' permission"
else
    fail "Missing 'actions: read' permission"
fi

echo ""
echo "Testing Failure Conditions..."
echo "-----------------------------"

# Test 6: Only runs on failures
IF_CONDITION=$(yq '.jobs.analyze-failure.if' "$WORKFLOW_FILE" 2>/dev/null || echo "")
if echo "$IF_CONDITION" | grep -q "failure"; then
    pass "Checks for workflow failure"
else
    fail "Should check for workflow failure"
fi

if echo "$IF_CONDITION" | grep -q "workflow_dispatch"; then
    pass "Allows manual dispatch"
else
    warn "Should allow manual dispatch for testing"
fi

echo ""
echo "Testing Root Cause Classification..."
echo "------------------------------------"

# Test 7: All 7 categories present
WORKFLOW_CONTENT=$(cat "$WORKFLOW_FILE")

declare -a CATEGORIES=(
    "Workflow Design Issues"
    "Workflow Config Issues"
    "Application Problems"
    "GitOps Repository Issues"
    "Infrastructure Issues"
    "Flaky Tests"
    "Other"
)

for category in "${CATEGORIES[@]}"; do
    if echo "$WORKFLOW_CONTENT" | grep -q "$category"; then
        pass "Has category: $category"
    else
        fail "Missing category: $category"
    fi
done

echo ""
echo "Testing Systematic Fix Preference..."
echo "------------------------------------"

# Test 8: Emphasizes systematic fixes
if echo "$WORKFLOW_CONTENT" | grep -qi "systematic"; then
    pass "Emphasizes SYSTEMATIC fixes"
else
    fail "Should emphasize systematic fixes over patches"
fi

if echo "$WORKFLOW_CONTENT" | grep -qi "prevent"; then
    pass "Focuses on prevention"
else
    warn "Should focus on preventing future failures"
fi

if echo "$WORKFLOW_CONTENT" | grep -qi "avoid.*patch"; then
    pass "Warns against patch fixes"
else
    warn "Should warn against patch fixes"
fi

echo ""
echo "Testing Safety Mechanisms..."
echo "---------------------------"

# Test 9: Safety rules
if echo "$WORKFLOW_CONTENT" | grep -q "NEVER auto-merge"; then
    pass "Prevents auto-merge"
else
    fail "Should prevent auto-merge"
fi

if echo "$WORKFLOW_CONTENT" | grep -q "NEVER push directly"; then
    pass "Prevents direct push to main"
else
    fail "Should prevent direct push to main"
fi

if echo "$WORKFLOW_CONTENT" | grep -q "ALWAYS create a branch"; then
    pass "Requires branch creation"
else
    fail "Should require branch creation"
fi

if echo "$WORKFLOW_CONTENT" | grep -q "lenaxia"; then
    pass "Assigns PR to reviewer (lenaxia)"
else
    fail "Should assign PR to lenaxia for review"
fi

echo ""
echo "Testing Workflow Steps..."
echo "------------------------"

# Test 10: Required steps present
STEPS=$(yq '.jobs.analyze-failure.steps[].name' "$WORKFLOW_FILE" 2>/dev/null || echo "")

if echo "$STEPS" | grep -q "Checkout"; then
    pass "Has checkout step"
else
    fail "Missing checkout step"
fi

if echo "$STEPS" | grep -q "OpenCode"; then
    pass "Has OpenCode installation step"
else
    fail "Missing OpenCode installation step"
fi

if echo "$STEPS" | grep -q "logs"; then
    pass "Has log download step"
else
    fail "Missing log download step"
fi

if echo "$STEPS" | grep -q "context"; then
    pass "Has context gathering step"
else
    fail "Missing PR/commit context gathering step"
fi

if echo "$STEPS" | grep -q "Analyze"; then
    pass "Has analysis step"
else
    fail "Missing failure analysis step"
fi

echo ""
echo "Testing Concurrency Control..."
echo "------------------------------"

# Test 11: Concurrency settings
CONCURRENCY=$(yq '.concurrency' "$WORKFLOW_FILE" 2>/dev/null || echo "")
if [ -n "$CONCURRENCY" ]; then
    pass "Has concurrency configuration"
    
    if echo "$CONCURRENCY" | grep -q "cancel-in-progress.*false"; then
        pass "Does not cancel in-progress runs"
    else
        warn "Should not cancel in-progress runs to preserve analysis"
    fi
else
    warn "Missing concurrency configuration"
fi

echo ""
echo "Testing Artifact Upload..."
echo "-------------------------"

# Test 12: Uploads analysis artifacts
if echo "$STEPS" | grep -q "artifact"; then
    pass "Uploads analysis artifacts"
else
    warn "Should upload analysis artifacts for debugging"
fi

echo ""
echo "Testing Environment Variables..."
echo "--------------------------------"

# Test 13: Required environment variables
ENV_VARS=$(yq '.jobs.analyze-failure.steps[] | select(.name == "Analyze failure with OpenCode") | .env' "$WORKFLOW_FILE" 2>/dev/null || echo "")

if echo "$ENV_VARS" | grep -q "OPENAI_API_KEY"; then
    pass "Has OPENAI_API_KEY environment variable"
else
    fail "Missing OPENAI_API_KEY environment variable"
fi

if echo "$ENV_VARS" | grep -q "GITHUB_TOKEN"; then
    pass "Has GITHUB_TOKEN environment variable"
else
    fail "Missing GITHUB_TOKEN environment variable"
fi

echo ""
echo "=================================="
echo "Validation Summary"
echo "=================================="

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo "The failure-analysis workflow is ready for production."
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ All critical checks passed with $WARNINGS warnings${NC}"
    echo "The workflow will work but consider addressing warnings."
    exit 0
else
    echo -e "${RED}✗ $ERRORS errors and $WARNINGS warnings found${NC}"
    echo "Please fix the errors before using this workflow."
    exit 1
fi
