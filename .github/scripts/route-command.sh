#!/usr/bin/env bash
# route-command.sh — GitHub Actions AI-command routing logic (single source of truth).
#
# Sourced by .github/workflows/ai-comment.yml's "Build prompt" step and exercised
# by tests/gharouter/route_test.go. Keeping the routing in one sourced script means
# the routing/hold-detection surface has a persistent regression guard instead of
# being untestable inline YAML.
#
# Inputs (read from the environment):
#   COMMENT_BODY  — the triggering issue/PR comment body
#   PR_URL        — github.event.issue.pull_request.url (non-empty when on a PR)
#   EVENT_NAME    — github.event_name (issue_comment | pull_request_review_comment)
#   OUT_FILE      — where to write the assembled prompt (default /tmp/opencode_prompt.txt)
#   PROMPTS_DIR   — directory containing context.md, core-rules.md, *.md prompts
#                   (default .github/prompts, relative to the repo root)
#
# Outputs (set as shell variables after route_command returns):
#   COMMAND     — the resolved command token (e.g. /design, /merge, /ai)
#   NOTE        — the collaborator's trailing text (command + --no-merge stripped)
#   HOLD_MERGE  — 1 if a code-change command was held via --no-merge, else 0
#   OUT_FILE    — the prompt file path that was written
#
# When executed directly (not sourced), runs route_command and prints the
# resolved vars as KEY=VALUE lines for ad-hoc testing/inspection.

set -euo pipefail

route_command() {
  local comment_body="${COMMENT_BODY:-}"
  local pr_url="${PR_URL:-}"
  local event_name="${EVENT_NAME:-}"
  local prompts_dir="${PROMPTS_DIR:-.github/prompts}"
  local out_file="${OUT_FILE:-/tmp/opencode_prompt.txt}"

  CONTEXT_FILE="${prompts_dir}/context.md"
  CORE_FILE="${prompts_dir}/core-rules.md"
  WORKFLOW_FILE="${prompts_dir}/code-change-workflow.md"
  OUT="$out_file"
  OUT_FILE="$out_file"

  # Detect which command was used (check start of comment first, then inline).
  # Each pattern requires the command keyword followed by end-of-string or
  # a space — this prevents false matches like /testing → /test or /fixing → /fix.
  COMMAND=""
  case "$comment_body" in
    /implement\ *|/implement) COMMAND="/implement" ;;
    /security\ *|/security)   COMMAND="/security" ;;
    /analyze\ *|/analyze)     COMMAND="/analyze" ;;
    /review\ *|/review)       COMMAND="/review" ;;
    /explain\ *|/explain)     COMMAND="/explain" ;;
    /triage\ *|/triage)       COMMAND="/triage" ;;
    /design\ *|/design)       COMMAND="/design" ;;
    /merge\ *|/merge)         COMMAND="/merge" ;;
    /test\ *|/test)           COMMAND="/test" ;;
    /fix\ *|/fix)             COMMAND="/fix" ;;
    /help\ *|/help)           COMMAND="/help" ;;
    /ai\ *|/ai)               COMMAND="/ai" ;;
    *" /implement "*) COMMAND="/implement" ;;
    *" /security "*)  COMMAND="/security" ;;
    *" /analyze "*)   COMMAND="/analyze" ;;
    *" /review "*)    COMMAND="/review" ;;
    *" /explain "*)   COMMAND="/explain" ;;
    *" /triage "*)    COMMAND="/triage" ;;
    *" /design "*)    COMMAND="/design" ;;
    *" /merge "*)     COMMAND="/merge" ;;
    *" /test "*)      COMMAND="/test" ;;
    *" /fix "*)       COMMAND="/fix" ;;
    *" /help "*)      COMMAND="/help" ;;
    *" /ai "*)        COMMAND="/ai" ;;
    *)               COMMAND="/ai" ;;
  esac

  NOTE="$(printf '%s' "$comment_body" | sed "s|.*${COMMAND}||" | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')"

  # Detect the --no-merge hold flag. It's a global modifier:
  # strip it from NOTE for EVERY command (so it never pollutes the
  # description/topic), but only ACT on it for the four auto-merging
  # code-change commands. `/design` always holds (enforced in its prompt);
  # `/merge` is the explicit merge and ignores the flag.
  #
  # TRAILING-ONLY: --no-merge is recognized as the flag ONLY when it is the
  # last non-whitespace token of the comment (the conventional "append"
  # position). This eliminates false positives where the literal token appears
  # mid-description — e.g. `/fix the --no-merge stripping is greedy` must NOT
  # hold and must NOT be mangled. A leading or mid position (`/implement
  # --no-merge add cache`) is treated as ordinary description text; users
  # append the flag at the end (`/implement add cache --no-merge`).
  HOLD_MERGE=0
  if printf '%s' "$comment_body" | grep -Eq '(^|[[:space:]])--no-merge[[:space:]]*$'; then
    # Strip the trailing flag token from NOTE.
    NOTE="$(printf '%s' "$NOTE" | sed -E 's/(^|[[:space:]])--no-merge[[:space:]]*$//; s/^[[:space:]]*//; s/[[:space:]]*$//')"
    case "$COMMAND" in
      /fix|/implement|/test|/security) HOLD_MERGE=1 ;;
    esac
  fi

  # Write context header + core rules
  cat "$CONTEXT_FILE" > "$OUT"
  printf '\n\n---\n\n' >> "$OUT"
  cat "$CORE_FILE" >> "$OUT"
  printf '\n\n---\n\n' >> "$OUT"

  # Route to command-specific prompt
  case "$COMMAND" in
    /review)
      cat "${prompts_dir}/pr-review.md" >> "$OUT"
      if [ -n "$NOTE" ]; then
        printf '\n\nAdditional review focus from collaborator:\n\n> %s\n' "$NOTE" >> "$OUT"
      fi
      printf '\n\nA collaborator requested an explicit review using `/review`.\n' >> "$OUT"
      ;;
    /fix)
      cat "${prompts_dir}/fix.md" >> "$OUT"
      printf '\n\n' >> "$OUT"
      cat "$WORKFLOW_FILE" >> "$OUT"
      if [ -n "$NOTE" ]; then
        printf '\n\nBug or issue to fix:\n\n> %s\n' "$NOTE" >> "$OUT"
      fi
      ;;
    /implement)
      cat "${prompts_dir}/implement.md" >> "$OUT"
      printf '\n\n' >> "$OUT"
      cat "$WORKFLOW_FILE" >> "$OUT"
      if [ -n "$NOTE" ]; then
        printf '\n\nFeature or story to implement:\n\n> %s\n' "$NOTE" >> "$OUT"
      fi
      ;;
    /test)
      cat "${prompts_dir}/test.md" >> "$OUT"
      printf '\n\n' >> "$OUT"
      cat "$WORKFLOW_FILE" >> "$OUT"
      if [ -n "$NOTE" ]; then
        printf '\n\nTarget to write or improve tests for:\n\n> %s\n' "$NOTE" >> "$OUT"
      fi
      ;;
    /security)
      cat "${prompts_dir}/security.md" >> "$OUT"
      printf '\n\n' >> "$OUT"
      cat "$WORKFLOW_FILE" >> "$OUT"
      if [ -n "$NOTE" ]; then
        printf '\n\nSecurity review focus:\n\n> %s\n' "$NOTE" >> "$OUT"
      fi
      ;;
    /analyze)
      cat "${prompts_dir}/analyze.md" >> "$OUT"
      if [ -n "$NOTE" ]; then
        printf '\n\nAnalysis focus:\n\n> %s\n' "$NOTE" >> "$OUT"
      fi
      ;;
    /explain)
      cat "${prompts_dir}/explain.md" >> "$OUT"
      if [ -n "$NOTE" ]; then
        printf '\n\nTopic to explain:\n\n> %s\n' "$NOTE" >> "$OUT"
      fi
      ;;
    /triage)
      cat "${prompts_dir}/triage.md" >> "$OUT"
      if [ -n "$NOTE" ]; then
        printf '\n\nTriage context:\n\n> %s\n' "$NOTE" >> "$OUT"
      fi
      ;;
    /design)
      cat "${prompts_dir}/design.md" >> "$OUT"
      printf '\n\n' >> "$OUT"
      cat "$WORKFLOW_FILE" >> "$OUT"
      if [ -n "$NOTE" ]; then
        printf '\n\nDesign focus / topic:\n\n> %s\n' "$NOTE" >> "$OUT"
      fi
      ;;
    /merge)
      cat "${prompts_dir}/merge.md" >> "$OUT"
      ;;
    /help)
      cat "${prompts_dir}/help.md" >> "$OUT"
      ;;
    /ai)
      if [ -n "$NOTE" ]; then
        printf 'A collaborator has asked:\n\n> %s\n\nAddress this request. For any code changes: create a feature branch, open a PR, never commit to main directly.\n' "$NOTE" >> "$OUT"
      elif [ -n "$pr_url" ] || [ "$event_name" = "pull_request_review_comment" ]; then
        cat "${prompts_dir}/pr-review.md" >> "$OUT"
        printf '\n\nA collaborator triggered a re-review by posting `/ai`. Re-assess the PR in full, taking into account all commits pushed since the last review. Note what changed since the previous review if one exists.\n' >> "$OUT"
      else
        cat "${prompts_dir}/issue-responder.md" >> "$OUT"
        printf '\n\nA collaborator triggered you by posting `/ai`. Analyze the full issue thread and take the appropriate action.\n' >> "$OUT"
      fi
      ;;
  esac

  # If --no-merge was passed on a code-change command, override the
  # Code Change Workflow's auto-merge (step 7). Placed last so it is the
  # final, unambiguous instruction. `/design` holds via its own prompt;
  # `/merge` is the explicit release and is never held.
  if [ "$HOLD_MERGE" = "1" ]; then
    printf '\n\n---\n\n**MERGE HOLD (`--no-merge`):** The collaborator passed `--no-merge` on this `%s`. Override Code Change Workflow step 7: after the automated review posts APPROVE, do NOT merge. Post a comment on the PR stating it is approved and awaiting an explicit `/merge` from a collaborator. Do not merge until `/merge` is received.\n' "$COMMAND" >> "$OUT"
  fi

  export COMMAND NOTE HOLD_MERGE OUT_FILE
}

# When executed directly (not sourced), run the router and print resolved vars.
if [ "${BASH_SOURCE[0]:-$0}" = "$0" ]; then
  route_command
  printf 'COMMAND=%s\nNOTE=%s\nHOLD_MERGE=%s\nOUT_FILE=%s\n' "$COMMAND" "$NOTE" "$HOLD_MERGE" "$OUT_FILE"
fi
