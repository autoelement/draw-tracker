#!/bin/bash
# Auto-create PR when feature branch has commits not in main

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
# Only run on feature branches
if [[ "$BRANCH" == "main" || "$BRANCH" == "" ]]; then exit 0; fi

# Check if branch has commits ahead of main
AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
if [[ "$AHEAD" == "0" ]]; then exit 0; fi

OWNER="autoelement"
REPO="draw-tracker"
API="https://api.github.com/repos/$OWNER/$REPO"

# Check if PR already exists for this branch
EXISTING=$(curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  "$API/pulls?state=open&head=$OWNER:$BRANCH" | grep -c '"number"')

if [[ "$EXISTING" -gt 0 ]]; then exit 0; fi

# Create PR
RESULT=$(curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  "$API/pulls" \
  -d "{\"title\":\"Updates from $BRANCH\",\"head\":\"$BRANCH\",\"base\":\"main\",\"body\":\"Auto-created PR from branch \`$BRANCH\`\"}")

PR_URL=$(echo "$RESULT" | grep -o '"html_url":"[^"]*pulls/[0-9]*"' | head -1 | cut -d'"' -f4)

if [[ -n "$PR_URL" ]]; then
  echo "{\"systemMessage\": \"✅ PR created: $PR_URL\"}"
fi
