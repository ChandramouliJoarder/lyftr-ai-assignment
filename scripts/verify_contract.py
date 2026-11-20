import os
import sys

# Set test environment
os.environ["LLM_API_KEYS"] = "key_1_test,key_2_test"
os.environ["ENABLE_FAILURE_SIMULATION"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///./verify_contract.db"

# Add backend directory to path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from app.main import app

def main():
    print("========================================")
    print("Testing Backend API Contract directly...")
    print("========================================")

    with TestClient(app) as client:
        # 1. Health
        h = client.get("/health")
        assert h.status_code == 200, f"Expected 200, got {h.status_code}"
        h_data = h.json()
        assert h_data == {"status": "ok", "keys_configured": 2, "cache_enabled": True}, f"Mismatch: {h_data}"
        print("✓ 1. GET /health -> 200", h_data)

        # 2. Validation 422
        v1 = client.post("/chat", json={"session_id": "s1", "message": "   "})
        assert v1.status_code == 422
        assert "detail" in v1.json()
        print("✓ 2. POST /chat whitespace-only -> 422 JSON detail")

        v2 = client.post("/chat", json={"session_id": "s1", "message": "a" * 4001})
        assert v2.status_code == 422
        print("✓ 3. POST /chat > 4000 chars -> 422")

        v3 = client.post("/chat", json={"message": "no session id"})
        assert v3.status_code == 422
        print("✓ 4. POST /chat missing session_id -> 422")

        # 3. 404 Unknown session
        u = client.get("/sessions/unknown-session-12345/messages")
        assert u.status_code == 404
        assert u.json() == {"detail": "session not found"}
        print("✓ 5. GET /sessions/unknown/messages -> 404 {'detail': 'session not found'}")

        # 4. Failover wildcard *=429 -> 503
        f = client.post(
            "/chat",
            json={"session_id": "s-failover-wildcard", "message": "Trigger failure"},
            headers={"X-Simulate-Failure": "*=429"},
        )
        assert f.status_code == 503
        assert f.json() == {"detail": "all providers unavailable"}
        print("✓ 6. POST /chat X-Simulate-Failure: *=429 -> 503 {'detail': 'all providers unavailable'}")

        # Check nothing added to history on 503
        h_check = client.get("/sessions/s-failover-wildcard/messages")
        assert h_check.status_code == 404
        assert h_check.json() == {"detail": "session not found"}
        print("✓ 7. Failed request (503) not added to SQLite history (404)")

    print("========================================")
    print("All direct contract tests PASSED!")
    print("========================================")

if __name__ == "__main__":
    main()
