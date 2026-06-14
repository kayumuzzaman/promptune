#!/usr/bin/env bash
# PostToolUse hook: remind to update docs when source files are edited.
# Fires after Edit/Write on promptune/ or tests/ files.

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only trigger for source/test files, not docs or config
if echo "$FILE_PATH" | grep -qE '(promptune/|tests/|pyproject\.toml)'; then
  # Don't trigger if this is already a doc edit
  if echo "$FILE_PATH" | grep -qE '\.(md|rst|txt)$'; then
    exit 0
  fi

  cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Reminder: Check if any docs need updating for this change (USER_GUIDE.md, CHANGELOG.md, README.md, specs, ARCHITECTURE.md). Update them if the changed behavior is documented there."
  }
}
EOF
fi
