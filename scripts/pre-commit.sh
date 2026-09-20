#!/usr/bin/env bash
#
# The checks that have to pass before a translation change leaves this machine.
#
# CI runs all of this on push, which is one commit too late: every fault found
# in the September translation review lived in an uncommitted working tree,
# where the source locales had been corrected and the generated pages under
# locales/pages/ and <lang>/ still carried the old text. Nothing looked wrong
# because nothing was looking.
#
# The layout check is deliberately absent — it needs headless Chrome and a
# local server, which is a minute per run. CI owns that one.
#
# Install:  ln -sf ../../scripts/pre-commit.sh .git/hooks/pre-commit
set -e

cd "$(git rev-parse --show-toplevel)"

# Only the things that feed the generator matter here. A commit that touches
# nothing but CSS should not pay for a rebuild.
if ! git diff --cached --name-only | grep -qE '^(locales/|tools/|assets/languages\.js|[a-z-]+\.html$)'; then
  exit 0
fi

echo "pre-commit: rebuilding generated pages"
python3 tools/build-pages.py >/dev/null

if ! git diff --quiet; then
  echo
  echo "  The generated output was stale and has just been rebuilt."
  echo "  Review the files below, 'git add' them, and commit again."
  echo
  git diff --stat
  exit 1
fi

# Deliberately without --strict, which CI does run. A missing key is always a
# fault and blocking it here is a kindness. A key nothing renders yet is the
# normal middle of a refactor — someone who has just deleted a section and not
# yet touched the locales should be able to commit that, and be stopped at the
# pull request instead. A hook that fires on work in progress gets --no-verify,
# and then it is not protecting anything at all.
echo "pre-commit: every rendered key exists in every language"
python3 tools/check-keys.py >/dev/null

echo "pre-commit: translations agree with themselves"
python3 tools/check-i18n.py >/dev/null

echo "pre-commit: ok"
