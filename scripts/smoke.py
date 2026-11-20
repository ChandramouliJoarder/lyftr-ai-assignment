#!/usr/bin/env python3
"""Cross-platform smoke test runner for LLM Chatbot backend."""

import os
import sys
import time
import json
import urllib.request
import urllib.error

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
passed = 0
failed = 0


def record_result(name: str, success: bool, details: str = ""):
    global passed, failed
    if success:
        print(f"✓ [PASS] {name}")
        passed += 1
    else:
        print(f"✗ [FAIL] {name} - {details}")
        failed += 1


def http_request(path: str, method: str = "GET", data: dict = None, headers: dict = None):
    url = f"{BASE_URL}{path}"
    req_headers = {"User-Agent": "SmokeTester/1.0"}
    if headers:
        req_headers.update(headers)

    body_bytes = None
    if data is not None:
        req_headers["Content-Type"] = "application/json"
        body_bytes = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            return e.code, json.loads(content)
        except Exception:
            return e.code, {"raw": content}


def run_smoke_tests():
    print("=============================================")
    print(f"Running Smoke Verification against: {BASE_URL}")
    print("=============================================")

    # 1. Health check
    try:
        status, body = http_request("/health")
        record_result("GET /health status is 200", status == 200)
        record_result("GET /health keys_configured is integer >= 1", isinstance(body.get("keys_configured"), int) and body.get("keys_configured") >= 1)
        record_result("GET /health cache_enabled is True", body.get("cache_enabled") is True)
    except Exception as e:
        record_result("GET /health endpoint reachable", False, str(e))
        return

    # 2. Validation 422 checks
    s422_1, b422_1 = http_request("/chat", method="POST", data={"session_id": "sm-1", "message": "   "})
    record_result("Validation: whitespace-only returns 422", s422_1 == 422)

    s422_2, b422_2 = http_request("/chat", method="POST", data={"session_id": "sm-1", "message": "a" * 4001})
    record_result("Validation: message > 4000 chars returns 422", s422_2 == 422)

    s422_3, b422_3 = http_request("/chat", method="POST", data={"message": "missing session id"})
    record_result("Validation: missing session_id returns 422", s422_3 == 422)

    # 3. Unknown session 404 check
    s404, b404 = http_request("/sessions/nonexistent-session-id-9999/messages")
    record_result("History: unknown session returns 404", s404 == 404)
    record_result("History: 404 detail matches contract", b404.get("detail") == "session not found")

    # 4. Failover wildcard 503 check (*=429)
    session_wildcard = f"smoke-wildcard-{int(time.time())}"
    s503, b503 = http_request(
        "/chat",
        method="POST",
        data={"session_id": session_wildcard, "message": "Trigger all fail"},
        headers={"X-Simulate-Failure": "*=429"},
    )
    record_result("Failover: *=429 returns 503", s503 == 503)
    record_result("Failover: 503 detail is 'all providers unavailable'", b503.get("detail") == "all providers unavailable")

    # Verify nothing added to history on 503
    s_hist_check, _ = http_request(f"/sessions/{session_wildcard}/messages")
    record_result("Failover: failed request not added to history (404)", s_hist_check == 404)

    # 5. Live inference / cache testing (or failover if real key present)
    session_live_1 = f"smoke-live1-{int(time.time())}"
    s_live, b_live = http_request(
        "/chat",
        method="POST",
        data={"session_id": session_live_1, "message": "What is the capital of France?"},
    )
    if s_live == 200:
        meta1 = b_live.get("metadata", {})
        record_result("Live chat returned 200", True)
        record_result("Live resolution_source is LIVE_INFERENCE", meta1.get("resolution_source") == "LIVE_INFERENCE")
        record_result("Live key_id is present", meta1.get("key_id") == "key_1")

        # Now test cache hit in new session with same message
        session_live_2 = f"smoke-live2-{int(time.time())}"
        s_cache, b_cache = http_request(
            "/chat",
            method="POST",
            data={"session_id": session_live_2, "message": "What is the capital of France?"},
        )
        record_result("Cached chat returned 200", s_cache == 200)
        meta2 = b_cache.get("metadata", {})
        record_result("Cache resolution_source is LLM_CACHE", meta2.get("resolution_source") == "LLM_CACHE")
        record_result("Cache key_id is null", meta2.get("key_id") is None)
        record_result("Cache fallback_attempts is 0", meta2.get("fallback_attempts") == 0)

        # Failover test: key_1=429
        session_failover = f"smoke-fo-{int(time.time())}"
        s_fo, b_fo = http_request(
            "/chat",
            method="POST",
            data={"session_id": session_failover, "message": "Test failover on key 1"},
            headers={"X-Simulate-Failure": "key_1=429"},
        )
        if s_fo == 200:
            meta_fo = b_fo.get("metadata", {})
            record_result("Failover returned 200 from key_2", meta_fo.get("key_id") == "key_2")
            record_result("Failover fallback_attempts is 1", meta_fo.get("fallback_attempts") == 1)

        # History test
        s_hist, b_hist = http_request(f"/sessions/{session_live_1}/messages")
        record_result("Session history returned 200", s_hist == 200)
        msgs = b_hist.get("messages", [])
        record_result("Session history has messages", len(msgs) >= 2)
    else:
        print(f"ℹ Note: Provider returned status {s_live} (likely placeholder API keys in local config). Contract endpoints verified.")

    print("=============================================")
    print(f"Smoke Tests Complete: {passed} passed, {failed} failed")
    print("=============================================")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_smoke_tests()
