#!/usr/bin/env bash
# Test scripts/setup-maas-key.sh in non-interactive mode (pipe).
# Verifies that only API_KEY/API_BASE/MODEL_PROVIDER/MODEL_NAME lines are
# changed and all other variables in the .env file are preserved untouched.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

# Create a temp .env file with existing variables — some that setup-maas-key.sh
# will replace, and some that must be preserved.
cat > "$T/test.env" <<'EOF'
API_BASE=https://old-base-url.example.com/v1
API_KEY=old-key-value-12345
MODEL_NAME=old-model
MODEL_PROVIDER=OldProvider
SOME_OTHER_KEY=foo
ANOTHER_VAR=bar
# A comment line
EMBED_API_BASE=
EMBED_API_KEY=
GITHUB_TOKEN=ghp_abcdef
EOF

# Run setup-maas-key.sh in non-interactive mode (pipe the key via stdin)
printf '%s\n' "test-secret-key-67890" \
  | "$ROOT/scripts/setup-maas-key.sh" --env-file "$T/test.env" --force > "$T/setup.out" 2>&1 \
  || { echo "FAIL: setup-maas-key.sh exited non-zero"; cat "$T/setup.out"; exit 1; }

# Verify the four target variables were updated
grep -q '^API_KEY=test-secret-key-67890$' "$T/test.env" \
  || { echo "FAIL: API_KEY not updated correctly"; cat "$T/test.env"; exit 1; }
grep -q '^API_BASE=https://api-ap-southeast-1.modelarts-maas.com/v1$' "$T/test.env" \
  || { echo "FAIL: API_BASE not updated to default"; cat "$T/test.env"; exit 1; }
grep -q '^MODEL_NAME=glm-5.2$' "$T/test.env" \
  || { echo "FAIL: MODEL_NAME not updated to default"; cat "$T/test.env"; exit 1; }
grep -q '^MODEL_PROVIDER=OpenAI$' "$T/test.env" \
  || { echo "FAIL: MODEL_PROVIDER not updated to OpenAI"; cat "$T/test.env"; exit 1; }

# Verify other variables are preserved
grep -q '^SOME_OTHER_KEY=foo$' "$T/test.env" \
  || { echo "FAIL: SOME_OTHER_KEY was modified"; cat "$T/test.env"; exit 1; }
grep -q '^ANOTHER_VAR=bar$' "$T/test.env" \
  || { echo "FAIL: ANOTHER_VAR was modified"; cat "$T/test.env"; exit 1; }
grep -q '^# A comment line$' "$T/test.env" \
  || { echo "FAIL: comment line was modified"; cat "$T/test.env"; exit 1; }
grep -q '^EMBED_API_BASE=$' "$T/test.env" \
  || { echo "FAIL: EMBED_API_BASE was modified"; cat "$T/test.env"; exit 1; }
grep -q '^EMBED_API_KEY=$' "$T/test.env" \
  || { echo "FAIL: EMBED_API_KEY was modified"; cat "$T/test.env"; exit 1; }
grep -q '^GITHUB_TOKEN=ghp_abcdef$' "$T/test.env" \
  || { echo "FAIL: GITHUB_TOKEN was modified"; cat "$T/test.env"; exit 1; }

# Verify the key does NOT appear in the script output (no leakage)
if grep -q 'test-secret-key-67890' "$T/setup.out"; then
  echo "FAIL: API key leaked in script output"
  cat "$T/setup.out"
  exit 1
fi

# ── Test with a .env file that doesn't have the variables yet (append) ──
cat > "$T/append.env" <<'EOF'
SOME_OTHER_KEY=foo
ANOTHER_VAR=bar
EOF

printf '%s\n' "new-key-value" \
  | "$ROOT/scripts/setup-maas-key.sh" --env-file "$T/append.env" --force > "$T/setup2.out" 2>&1 \
  || { echo "FAIL: setup-maas-key.sh exited non-zero on append test"; cat "$T/setup2.out"; exit 1; }

grep -q '^API_KEY=new-key-value$' "$T/append.env" \
  || { echo "FAIL: API_KEY not appended"; cat "$T/append.env"; exit 1; }
grep -q '^API_BASE=' "$T/append.env" \
  || { echo "FAIL: API_BASE not appended"; cat "$T/append.env"; exit 1; }
grep -q '^MODEL_NAME=' "$T/append.env" \
  || { echo "FAIL: MODEL_NAME not appended"; cat "$T/append.env"; exit 1; }
grep -q '^MODEL_PROVIDER=' "$T/append.env" \
  || { echo "FAIL: MODEL_PROVIDER not appended"; cat "$T/append.env"; exit 1; }
grep -q '^SOME_OTHER_KEY=foo$' "$T/append.env" \
  || { echo "FAIL: existing var lost during append"; cat "$T/append.env"; exit 1; }

echo "SETUP MAAS KEY: pass (API_KEY/API_BASE/MODEL_PROVIDER/MODEL_NAME updated, other vars preserved, key not leaked in output, append mode works for new files)"
