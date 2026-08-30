#!/usr/bin/env bash
# Build deploy.zip for Azure App Service: code + frozen plans + fixtures,
# NO secrets (.env stays local; keys go into App Service settings).
set -euo pipefail
cd "$(dirname "$0")/../.."

B=$(mktemp -d)
cp -R iqr webapp pyproject.toml "$B/"
mkdir -p "$B/tests" "$B/data"
cp tests/__init__.py tests/conftest.py "$B/tests/"
cp -R tests/fixtures "$B/tests/"
cp -R data/plans "$B/data/"
find "$B" -name __pycache__ -type d -prune -exec rm -rf {} +
find "$B" -name "*.pyc" -delete

python3 - "$B" <<'EOF'
import sys, tomllib
b = sys.argv[1]
deps = tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]
open(f"{b}/requirements.txt", "w").write("\n".join(deps) + "\n.\n")
EOF

rm -f deploy.zip
(cd "$B" && zip -qr "$OLDPWD/deploy.zip" .)
rm -rf "$B"
echo "deploy.zip ready: $(du -h deploy.zip | cut -f1)"
