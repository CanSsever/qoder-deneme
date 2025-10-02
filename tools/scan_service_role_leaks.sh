#!/usr/bin/env bash
set -euo pipefail
RG="rg"; command -v rg >/dev/null 2>&1 || RG="grep -R"
violations=$($RG -n "service_client\(|Supa\.service\(\)" backend/apps | grep -v "entitlements\.py" | grep -v "tools" || true)
if [ -n "$violations" ]; then
  echo "Service role found in user paths:"
  echo "$violations"
  exit 1
fi
echo "No service role leaks"