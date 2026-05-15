#!/usr/bin/env bash
set -e
printf "Checking active frontend source...\n"
grep -R "LMCP AutoQuote Command Centre" -n src/App.jsx
grep -R "Autonomous Tender Control Tower" -n src/App.jsx
if grep -R "LMCP Autonomous Tender System" -n src/App.jsx src 2>/dev/null; then
  echo "ERROR: old UI text still exists in this folder."
  exit 1
fi
echo "OK: corrected command-centre UI source is present."
