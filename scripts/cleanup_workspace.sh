#!/bin/bash
#
# Talk2YourServer - Claude Workspace Cleanup Script
# Removes files older than specified days from the Claude workspace
#
# Usage: ./cleanup_workspace.sh [days]
# Default: 15 days
#
# Cron example (daily at 3 AM):
# 0 3 * * * /path/to/talk2yourServer/scripts/cleanup_workspace.sh
#

# Configuration - adjust these paths
WORKSPACE="${WORKSPACE_DIR:-$HOME/claude_workspace}"
LOG_DIR="${LOG_DIR:-$(dirname "$0")/../logs}"
LOG_FILE="$LOG_DIR/cleanup.log"
DAYS_OLD="${1:-15}"

# Create log directory if needed
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Safety check - workspace must exist
if [ ! -d "$WORKSPACE" ]; then
    log "ERROR: Workspace directory does not exist: $WORKSPACE"
    echo "ERROR: Workspace directory does not exist: $WORKSPACE"
    exit 1
fi

# Extra safety - verify workspace is in home directory
case "$WORKSPACE" in
    "$HOME"/*)
        # OK - workspace is under home directory
        ;;
    *)
        log "ERROR: Workspace must be under home directory for safety"
        echo "ERROR: Workspace must be under home directory for safety"
        exit 1
        ;;
esac

# Count files before cleanup
BEFORE_COUNT=$(find "$WORKSPACE" -type f 2>/dev/null | wc -l)

# Find and delete files older than specified days
# -mtime +N means modified more than N days ago
DELETED_FILES=$(find "$WORKSPACE" -type f -mtime +$DAYS_OLD -print -delete 2>/dev/null)

# Find and delete empty directories (except the workspace root)
find "$WORKSPACE" -mindepth 1 -type d -empty -delete 2>/dev/null

# Count files after cleanup
AFTER_COUNT=$(find "$WORKSPACE" -type f 2>/dev/null | wc -l)

# Calculate deleted count
DELETED_COUNT=$((BEFORE_COUNT - AFTER_COUNT))

if [ $DELETED_COUNT -gt 0 ]; then
    log "Cleanup completed: Deleted $DELETED_COUNT files older than $DAYS_OLD days"
    if [ -n "$DELETED_FILES" ]; then
        log "Deleted files:"
        echo "$DELETED_FILES" | while read -r file; do
            log "  - $file"
        done
    fi
else
    log "Cleanup completed: No files older than $DAYS_OLD days found"
fi

# Report current workspace size
SIZE=$(du -sh "$WORKSPACE" 2>/dev/null | cut -f1)
FILE_COUNT=$(find "$WORKSPACE" -type f 2>/dev/null | wc -l)
log "Current workspace: $SIZE, $FILE_COUNT files"

# Rotate log if too big (>1MB)
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(stat -c%s "$LOG_FILE" 2>/dev/null || stat -f%z "$LOG_FILE" 2>/dev/null || echo "0")
    if [ "$LOG_SIZE" -gt 1048576 ]; then
        mv "$LOG_FILE" "$LOG_FILE.old"
        log "Log rotated"
    fi
fi

echo "Cleanup completed. Deleted $DELETED_COUNT files. See $LOG_FILE for details."
