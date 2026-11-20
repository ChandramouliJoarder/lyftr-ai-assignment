#!/usr/bin/env bash
# Smoke test script for LLM Chatbot backend
set -e

BASE_URL="${API_BASE_URL:-http://localhost:8000}"
PASSED=0
FAILED=0

echo "============================================="
echo "Running Smoke Verification against: $BASE_URL"
echo "============================================="

check_test() {
  local name="$1"
  local expected="$2"
  local actual="$3"

  if echo "$actual" | grep -q "$expected"; then
    echo "✓ [PASS] $name"
    PASSED=$((PASSED + 1))
  else
    echo "✗ [FAIL] $name"
    echo "  Expected to find: $expected"
    echo "  Actual response: $actual"
    FAILED=$((FAILED + 1))
  fi
}

# 1. Test /health
echo "Testing GET /health..."
HEALTH_RESP=$(curl -s "$BASE_URL/health")
check_test "Health endpoint status" '"status":"ok"' "$HEALTH_RESP"
check_test "Health endpoint cache" '"cache_enabled":true' "$HEALTH_RESP"

# 2. Test /chat happy path (LIVE_INFERENCE)
echo "Testing POST /chat (Live inference)..."
SESSION_1="smoke-s-$(date +%s)"
CHAT_RESP_1=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_1\",\"message\":\"Smoke test prompt capital of France?\"}")
check_test "Live inference resolution_source" '"resolution_source":"LIVE_INFERENCE"' "$CHAT_RESP_1"
check_test "Live inference key_id" '"key_id":"key_1"' "$CHAT_RESP_1"

# 3. Test /chat response caching in NEW session (expect LLM_CACHE)
echo "Testing POST /chat caching in new session..."
SESSION_2="smoke-s-new-$(date +%s)"
CHAT_RESP_2=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_2\",\"message\":\"Smoke test prompt capital of France?\"}")
check_test "Cache resolution_source" '"resolution_source":"LLM_CACHE"' "$CHAT_RESP_2"
check_test "Cache key_id is null" '"key_id":null' "$CHAT_RESP_2"

# 4. Test failover: key_1=429 (failover to key_2)
echo "Testing POST /chat failover (key_1=429)..."
SESSION_3="smoke-s-failover-$(date +%s)"
CHAT_RESP_3=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d "{\"session_id\":\"$SESSION_3\",\"message\":\"Failover test on key 1\"}")
check_test "Failover key_2 answered" '"key_id":"key_2"' "$CHAT_RESP_3"
check_test "Fallback attempts count" '"fallback_attempts":1' "$CHAT_RESP_3"

# 5. Test all keys fail: *=429 (expect 503)
echo "Testing POST /chat all fail (*=429)..."
SESSION_4="smoke-s-allfail-$(date +%s)"
HTTP_CODE_503=$(curl -s -o /tmp/resp_503.json -w "%{http_code}" -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: *=429" \
  -d "{\"session_id\":\"$SESSION_4\",\"message\":\"All keys fail test\"}")
BODY_503=$(cat /tmp/resp_503.json 2>/dev/null || echo "")
check_test "All providers unavailable status 503" "503" "$HTTP_CODE_503"
check_test "All providers unavailable body" '"detail":"all providers unavailable"' "$BODY_503"

# 6. Test GET /sessions/{id}/messages
echo "Testing GET /sessions/{session_id}/messages..."
HIST_RESP=$(curl -s "$BASE_URL/sessions/$SESSION_1/messages")
check_test "Session history returned" "\"session_id\":\"$SESSION_1\"" "$HIST_RESP"
check_test "Session history role user" '"role":"user"' "$HIST_RESP"
check_test "Session history role assistant" '"role":"assistant"' "$HIST_RESP"

echo "============================================="
echo "Smoke Tests Summary: $PASSED passed, $FAILED failed"
echo "============================================="

if [ "$FAILED" -ne 0 ]; then
  exit 1
fi
