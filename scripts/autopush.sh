#!/bin/bash
# Auto-push data.json changes to GitHub Pages
# Triggered by launchd when data.json is modified

cd /Users/sizovaka/Documents/AI_LAB/GitHub/blr-board || exit 1

# Check if there are actual changes
if git diff --quiet data.json 2>/dev/null; then
  exit 0
fi

# Update timestamp before push
NOW=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
/usr/bin/sed -i '' "s/\"updated_at\": \"[^\"]*\"/\"updated_at\": \"$NOW\"/" data.json
/usr/bin/sed -i '' "s/\"updated\": \"[^\"]*\"/\"updated\": \"$(date +%Y-%m-%d)\"/" data.json

git add data.json
git commit -m "auto: board update $(date +%Y-%m-%d_%H:%M)"
git push
