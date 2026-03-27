#!/bin/bash
# Auto-push data.json changes to GitHub Pages
# Triggered by launchd when data.json is modified

cd /Users/sizovaka/Documents/AI_LAB/GitHub/blr-board || exit 1

# Check if there are actual changes
if git diff --quiet data.json 2>/dev/null; then
  exit 0
fi

git add data.json
git commit -m "auto: board update $(date +%Y-%m-%d_%H:%M)"
git push
