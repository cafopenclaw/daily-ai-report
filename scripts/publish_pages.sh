#!/bin/zsh
set -euo pipefail

ROOT_DIR="/Users/colefosteropenclaw/.openclaw/workspace/daily-ai-report"
WORKTREE_DIR="$ROOT_DIR/.worktree-gh-pages"

cd "$ROOT_DIR"

# 1) Generate fresh HTML into ./site
/usr/bin/python3 "$ROOT_DIR/scripts/generate_report.py" >/dev/null

# 2) Ensure we have a gh-pages branch worktree
if [ ! -d "$WORKTREE_DIR" ]; then
  # Create orphan gh-pages branch if it doesn't exist
  if git show-ref --verify --quiet refs/heads/gh-pages; then
    git worktree add "$WORKTREE_DIR" gh-pages
  else
    git worktree add --detach "$WORKTREE_DIR"
    cd "$WORKTREE_DIR"
    git checkout --orphan gh-pages
    git rm -rf . >/dev/null 2>&1 || true
    echo "# Daily AI Report" > README.md
    git add README.md
    git commit -m "Initialize gh-pages" >/dev/null
    cd "$ROOT_DIR"
  fi
fi

# 3) Copy site/* into the gh-pages worktree root
cd "$WORKTREE_DIR"

# Clean everything except .git
find . -mindepth 1 -maxdepth 1 -not -name ".git" -exec rm -rf {} +

cp -R "$ROOT_DIR/site/." "$WORKTREE_DIR/"

# Ensure GitHub Pages has an index.html
if [ ! -f "$WORKTREE_DIR/index.html" ]; then
  echo "Missing index.html" >&2
  exit 1
fi

git add -A
if git diff --cached --quiet; then
  exit 0
fi

git commit -m "Update report $(date +%Y-%m-%d)" >/dev/null

# Push
# NOTE: requires git credentials set up on this machine.
git push -f origin gh-pages
