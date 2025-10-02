#!/usr/bin/env bash
set -euo pipefail
red(){ printf "\033[31m%s\033[0m\n" "$*"; }
grn(){ printf "\033[32m%s\033[0m\n" "$*"; }
pass(){ grn "PASS: $*"; }
fail(){ red "FAIL: $*"; exit 1; }

RG="rg"; command -v rg >/dev/null 2>&1 || RG="grep -R"

# Required files
need=(
  "docs/migration/users.md"
  "tools/invite_existing_users.py"
  "docs/migration/etl.md"
  "backend/apps/core/supa_request.py"
  "supabase/patch_storage_policies.sql"
  "backend/tests/smoke_rls.sh"
  "Makefile"
)
for f in "${need[@]}"; do [ -f "$f" ] || fail "missing $f"; done; pass "required files exist"

# Runtime request path must NOT use legacy bits
$RG -n "(sqlmodel|Session|get_session|boto3|s3|create_access_token|jwt\.encode)" backend/apps/api && fail "legacy code found in request path" || pass "no legacy in request path"

# Service role must NOT be used in user flows (allowlist entitlements + tools)
$RG -n "service_client\(|Supa\.service\(\)" backend/apps | grep -v "entitlements\.py" | grep -v "tools" | grep -v "invite_existing_users\.py" && fail "service role leak in user paths" || pass "no service role leaks in user paths"

# Make sure MODEL_PROVIDER default mock (optional best-effort)
$RG -n "MODEL_PROVIDER" backend || pass "MODEL_PROVIDER not enforced (ok)"
echo "OK"