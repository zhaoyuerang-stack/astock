#!/bin/zsh
set -euo pipefail

ROOT="/Users/kiki/astcok/factor_research"
AGENTS="$HOME/Library/LaunchAgents"

mkdir -p "$AGENTS"
mkdir -p "$ROOT/logs/daily_update" "$ROOT/logs/weekly_maintenance"
mkdir -p "$ROOT/reports/ops/daily_update" "$ROOT/reports/ops/weekly_maintenance"

cp "$ROOT/scripts/ops/com.astcok.daily-update.plist" "$AGENTS/com.astcok.daily-update.plist"
cp "$ROOT/scripts/ops/com.astcok.weekly-maintenance.plist" "$AGENTS/com.astcok.weekly-maintenance.plist"

launchctl bootout "gui/$UID" "$AGENTS/com.astcok.daily-update.plist" 2>/dev/null || true
launchctl bootout "gui/$UID" "$AGENTS/com.astcok.weekly-maintenance.plist" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$AGENTS/com.astcok.daily-update.plist"
launchctl bootstrap "gui/$UID" "$AGENTS/com.astcok.weekly-maintenance.plist"

echo "Installed launchd jobs:"
echo "  com.astcok.daily-update        weekdays 00:30 and 01:30 local time; script gates at China 16:30"
echo "  com.astcok.weekly-maintenance  Sunday 02:30 local time"
echo
echo "Manual trigger:"
echo "  launchctl kickstart -k gui/$UID/com.astcok.daily-update"
echo "  launchctl kickstart -k gui/$UID/com.astcok.weekly-maintenance"
