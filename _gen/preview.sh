#!/bin/sh
# Build, check, and copy the site to where the Claude app's preview server can read it.
# The preview server is not allowed into ~/Documents, so it serves this copy
# (.claude/launch.json in the app repo, "charactersheet-site", http://localhost:4173).
# In a terminal of your own no copy is needed:
#   python3 -m http.server 4173 --directory website
set -e
SITE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$HOME/Library/Caches/charactersheet-site"
(cd "$SITE/_gen" && python3 build.py >/dev/null)
python3 "$SITE/_gen/check.py"
mkdir -p "$OUT"
rsync -a --delete --exclude .git --exclude _gen --exclude .gitignore "$SITE/" "$OUT/"
echo "synced to $OUT"
