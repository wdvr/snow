#!/bin/bash
# Stop hook: remind Claude to update DIARY.md when there are new commits today
# Returns exit code 2 (blocking) if diary needs updating, 0 otherwise

DIARY="$CLAUDE_PROJECT_DIR/DIARY.md"
TODAY=$(date +%Y-%m-%d)

# Skip if no DIARY.md exists
[ ! -f "$DIARY" ] && exit 0

# Check if there are commits from today
COMMITS_TODAY=$(git -C "$CLAUDE_PROJECT_DIR" log --oneline --since="$TODAY 00:00:00" --until="$TODAY 23:59:59" 2>/dev/null | wc -l | tr -d ' ')
[ "$COMMITS_TODAY" -eq 0 ] && exit 0

# Check if DIARY.md was modified in one of today's commits
DIARY_COMMITTED_TODAY=$(git -C "$CLAUDE_PROJECT_DIR" log --oneline --since="$TODAY 00:00:00" --until="$TODAY 23:59:59" -- DIARY.md 2>/dev/null | wc -l | tr -d ' ')

# Check if DIARY.md has uncommitted changes (staged or unstaged)
DIARY_DIRTY=$(git -C "$CLAUDE_PROJECT_DIR" diff --name-only -- DIARY.md 2>/dev/null; git -C "$CLAUDE_PROJECT_DIR" diff --cached --name-only -- DIARY.md 2>/dev/null)

# If diary was committed today OR has pending changes, it's been updated — all good
if [ "$DIARY_COMMITTED_TODAY" -gt 0 ] || [ -n "$DIARY_DIRTY" ]; then
    exit 0
fi

# Diary not updated but there are commits today — block and remind
echo "You made $COMMITS_TODAY commit(s) today but DIARY.md hasn't been updated. Update DIARY.md with entries for today's changes before finishing. Format: ### Title, description, then platform status table (iOS|Android|Web|API with done/pending/n/a/backlog)." >&2
exit 2
