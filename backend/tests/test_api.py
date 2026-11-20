import os
import tempfile
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# Mock environment variables before importing app
os.environ["LLM_API_KEYS"] = "mock_secret_key_1,mock_secret_key_2"
os.environ["ENABLE_FAILURE_SIMULATION"] = "true"
os.environ["LLM_MODEL"] = "gemini/gemini-2.0-flash"

import litellm
from app.config import settings
from app.db import Database, db
from app.main import app
import app.llm as app_llm


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Use a clean temporary database and disk cache for each test."""
    temp_db_path = str(tmp_path / "test.db")
    temp_cache_dir = str(tmp_path / "cache")
    os.makedirs(temp_cache_dir, exist_ok=True)

    test_db = Database(f"sqlite:///{temp_db_path}")
    test_db.init_schema()

    monkeypatch.setattr("app.main.db", test_db)
    monkeypatch.setattr("app.llm.db", test_db)
    monkeypatch.setattr("app.db.db", test_db)

    # Re-init LiteLLM cache
    from litellm.caching.caching import Cache
    litellm.cache = Cache(type="local")
    monkeypatch.setattr(app_llm, "cache_enabled", True)

    yield test_db


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def make_mock_completion_response(content: str = "Mocked reply", prompt_tokens: int = 15, completion_tokens: int = 8):
    """Create a mock LiteLLM completion response object."""
    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(message=MagicMock(content=content))
    ]
    mock_resp.usage = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    mock_resp._hidden_params = {}
    return mock_resp


def test_health_endpoint(client):
    """GET /health returns exact shape, keys_configured, and cache_enabled."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["keys_configured"] == 2
    assert data["cache_enabled"] is True


def test_chat_happy_path(client, monkeypatch):
    """POST /chat happy path returns 200 with required metadata."""
    def mock_completion(**kwargs):
        return make_mock_completion_response("Paris is the capital of France.", 25, 7)

    monkeypatch.setattr(litellm, "completion", mock_completion)

    payload = {
        "session_id": "test-s1",
        "message": "What is the capital of France?",
    }
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["session_id"] == "test-s1"
    assert data["reply"] == "Paris is the capital of France."

    meta = data["metadata"]
    assert meta["resolution_source"] == "LIVE_INFERENCE"
    assert meta["model"] == "gemini/gemini-2.0-flash"
    assert isinstance(meta["latency_ms"], int)
    assert meta["latency_ms"] >= 0
    assert meta["input_tokens"] == 25
    assert meta["output_tokens"] == 7
    assert meta["key_id"] == "key_1"
    assert meta["fallback_attempts"] == 0

    # Verify no raw keys leaked
    assert "mock_secret_key" not in resp.text


def test_response_caching_and_tokens(client, monkeypatch):
    """
    Same first message in a NEW session must return LLM_CACHE, identical reply,
    key_id=None, fallback_attempts=0, and identical token usage.
    """
    call_count = 0

    def mock_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        return make_mock_completion_response("Cached answer test.", 42, 12)

    monkeypatch.setattr(litellm, "completion", mock_completion)

    # Turn 1 in session-A -> LIVE_INFERENCE
    resp1 = client.post("/chat", json={
        "session_id": "session-A",
        "message": "Explain quantum computing briefly",
    })
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert d1["metadata"]["key_id"] == "key_1"
    assert d1["metadata"]["input_tokens"] == 42
    assert d1["metadata"]["output_tokens"] == 12
    assert call_count == 1

    # Turn 1 in NEW session-B with SAME message -> LLM_CACHE
    resp2 = client.post("/chat", json={
        "session_id": "session-B",
        "message": "Explain quantum computing briefly",
    })
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["metadata"]["resolution_source"] == "LLM_CACHE"
    assert d2["reply"] == d1["reply"]
    assert d2["metadata"]["key_id"] is None
    assert d2["metadata"]["fallback_attempts"] == 0
    assert d2["metadata"]["input_tokens"] == 42
    assert d2["metadata"]["output_tokens"] == 12
    # Ensure provider completion was NOT called again
    assert call_count == 1

    # Different message in session-C -> LIVE_INFERENCE
    resp3 = client.post("/chat", json={
        "session_id": "session-C",
        "message": "Tell me a completely different story",
    })
    assert resp3.status_code == 200
    d3 = resp3.json()
    assert d3["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert call_count == 2


def test_multi_turn_history(client, monkeypatch):
    """Second message includes first message in messages sent to LLM."""
    recorded_messages = []

    def mock_completion(**kwargs):
        recorded_messages.append(kwargs.get("messages", []))
        return make_mock_completion_response(f"Reply {len(recorded_messages)}", 20, 5)

    monkeypatch.setattr(litellm, "completion", mock_completion)

    client.post("/chat", json={"session_id": "mt-1", "message": "Hello, I am Alice"})
    client.post("/chat", json={"session_id": "mt-1", "message": "What is my name?"})

    assert len(recorded_messages) == 2
    # First turn: system + user
    assert recorded_messages[0][0]["role"] == "system"
    assert recorded_messages[0][1] == {"role": "user", "content": "Hello, I am Alice"}

    # Second turn: system + user1 + assistant1 + user2
    msgs2 = recorded_messages[1]
    assert msgs2[0]["role"] == "system"
    assert msgs2[1] == {"role": "user", "content": "Hello, I am Alice"}
    assert msgs2[2] == {"role": "assistant", "content": "Reply 1"}
    assert msgs2[3] == {"role": "user", "content": "What is my name?"}

    # Isolated session
    client.post("/chat", json={"session_id": "mt-2", "message": "Who am I?"})
    assert len(recorded_messages) == 3
    msgs3 = recorded_messages[2]
    # Should only contain system + mt-2 user message
    assert len(msgs3) == 2
    assert msgs3[1] == {"role": "user", "content": "Who am I?"}


def test_custom_system_prompt_persistence(client, monkeypatch):
    """System prompt overrides default and persists across turns in session."""
    recorded_prompts = []

    def mock_completion(**kwargs):
        msgs = kwargs.get("messages", [])
        recorded_prompts.append(msgs[0]["content"])
        return make_mock_completion_response("Reply", 10, 5)

    monkeypatch.setattr(litellm, "completion", mock_completion)

    client.post("/chat", json={
        "session_id": "sys-session",
        "message": "First message",
        "system_prompt": "You are a pirate.",
    })
    # Second turn omits system_prompt
    client.post("/chat", json={
        "session_id": "sys-session",
        "message": "Second message",
    })

    assert len(recorded_prompts) == 2
    assert recorded_prompts[0] == "You are a pirate."
    assert recorded_prompts[1] == "You are a pirate."


def test_history_endpoint(client, monkeypatch):
    """GET /sessions/{session_id}/messages returns stored history without system prompt."""
    def mock_completion(**kwargs):
        return make_mock_completion_response("Assistant response text", 30, 10)

    monkeypatch.setattr(litellm, "completion", mock_completion)

    # 404 for non-existent session
    resp404 = client.get("/sessions/unknown-session-123/messages")
    assert resp404.status_code == 404
    assert resp404.json() == {"detail": "session not found"}

    # Create session with 2 turns
    client.post("/chat", json={"session_id": "hist-1", "message": "Msg 1"})
    client.post("/chat", json={"session_id": "hist-1", "message": "Msg 2"})

    resp = client.get("/sessions/hist-1/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "hist-1"
    messages = data["messages"]
    assert len(messages) == 4

    # Order check: user1, assistant1, user2, assistant2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Msg 1"
    assert messages[0].get("metadata") is None

    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Assistant response text"
    assert messages[1]["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert messages[1]["metadata"]["input_tokens"] == 30
    assert messages[1]["metadata"]["output_tokens"] == 10

    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "Msg 2"

    assert messages[3]["role"] == "assistant"


def test_validation_errors(client):
    """Validation: empty, whitespace-only, 4001 chars, invalid session_id return 422 and nothing added."""
    # Whitespace-only message
    r1 = client.post("/chat", json={"session_id": "v-1", "message": "   "})
    assert r1.status_code == 422
    assert "detail" in r1.json()

    # Empty message
    r2 = client.post("/chat", json={"session_id": "v-1", "message": ""})
    assert r2.status_code == 422

    # Message over 4000 characters
    r3 = client.post("/chat", json={"session_id": "v-1", "message": "a" * 4001})
    assert r3.status_code == 422

    # Missing session_id
    r4 = client.post("/chat", json={"message": "hello"})
    assert r4.status_code == 422

    # Session_id over 128 chars
    r5 = client.post("/chat", json={"session_id": "s" * 129, "message": "hello"})
    assert r5.status_code == 422

    # Malformed JSON
    r6 = client.post(
        "/chat",
        content="{ bad json",
        headers={"Content-Type": "application/json"},
    )
    assert r6.status_code == 422

    # Verify nothing was added to history
    r_check = client.get("/sessions/v-1/messages")
    assert r_check.status_code == 404


def test_failover_simulation_headers(client, monkeypatch):
    """
    Test X-Simulate-Failure:
    - key_1=429 -> 200, key_id = key_2, fallback_attempts = 1
    - key_1=500 -> 200, key_id = key_2, fallback_attempts = 1
    - *=429 -> 503 {"detail": "all providers unavailable"}, nothing added to history
    """
    def mock_completion(**kwargs):
        return make_mock_completion_response("Failover answered successfully", 18, 6)

    monkeypatch.setattr(litellm, "completion", mock_completion)

    # Case 1: key_1=429 -> failover to key_2
    resp1 = client.post(
        "/chat",
        json={"session_id": "sim-1", "message": "Testing 429 on key 1"},
        headers={"X-Simulate-Failure": "key_1=429"},
    )
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1["metadata"]["key_id"] == "key_2"
    assert d1["metadata"]["fallback_attempts"] == 1

    # Case 2: key_1=500 -> failover to key_2
    resp2 = client.post(
        "/chat",
        json={"session_id": "sim-2", "message": "Testing 500 on key 1"},
        headers={"X-Simulate-Failure": "key_1=500"},
    )
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["metadata"]["key_id"] == "key_2"
    assert d2["metadata"]["fallback_attempts"] == 1

    # Case 3: *=429 -> all keys fail -> 503
    resp3 = client.post(
        "/chat",
        json={"session_id": "sim-3", "message": "Testing all keys fail"},
        headers={"X-Simulate-Failure": "*=429"},
    )
    assert resp3.status_code == 503
    assert resp3.json() == {"detail": "all providers unavailable"}

    # Ensure nothing added to history on 503
    r_hist = client.get("/sessions/sim-3/messages")
    assert r_hist.status_code == 404

    # Case 4: key_1=429,key_2=500 -> all keys fail -> 503
    resp4 = client.post(
        "/chat",
        json={"session_id": "sim-4", "message": "Testing multi keys fail"},
        headers={"X-Simulate-Failure": "key_1=429,key_2=500"},
    )
    assert resp4.status_code == 503
    assert resp4.json() == {"detail": "all providers unavailable"}


def test_simulation_header_disabled_flag(client, monkeypatch):
    """When ENABLE_FAILURE_SIMULATION is false, X-Simulate-Failure is ignored."""
    monkeypatch.setattr(settings, "ENABLE_FAILURE_SIMULATION", False)

    def mock_completion(**kwargs):
        return make_mock_completion_response("Normal answer", 10, 4)

    monkeypatch.setattr(litellm, "completion", mock_completion)

    # Even with *=429, it should succeed on key_1 because simulation is disabled
    resp = client.post(
        "/chat",
        json={"session_id": "disabled-sim", "message": "Should succeed"},
        headers={"X-Simulate-Failure": "*=429"},
    )
    assert resp.status_code == 200
    assert resp.json()["metadata"]["key_id"] == "key_1"
    assert resp.json()["metadata"]["fallback_attempts"] == 0


def test_real_provider_exceptions_trigger_failover(client, monkeypatch):
    """Real LiteLLM RateLimitError on first key triggers failover to key_2."""
    attempt_keys = []

    def mock_completion(**kwargs):
        key = kwargs.get("api_key")
        attempt_keys.append(key)
        if key == "mock_secret_key_1":
            raise litellm.RateLimitError(
                message="Resource exhausted",
                llm_provider="gemini",
                model="gemini/gemini-2.0-flash",
            )
        return make_mock_completion_response("Key 2 succeeded", 22, 9)

    monkeypatch.setattr(litellm, "completion", mock_completion)

    resp = client.post(
        "/chat",
        json={"session_id": "real-failover", "message": "Trigger real failover"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"]["key_id"] == "key_2"
    assert data["metadata"]["fallback_attempts"] == 1
    assert attempt_keys == ["mock_secret_key_1", "mock_secret_key_2"]


def test_persistence_across_instances(tmp_path, monkeypatch):
    """Data written is readable when re-opening the SQLite database file."""
    db_file = str(tmp_path / "persistent.db")
    db1 = Database(f"sqlite:///{db_file}")
    db1.init_schema()
    db1.save_turn(
        session_id="p-1",
        user_content="Hello persistent world",
        assistant_content="Stored safely",
        assistant_metadata={"resolution_source": "LIVE_INFERENCE", "input_tokens": 5, "output_tokens": 2},
    )

    # Second database instance on the same file
    db2 = Database(f"sqlite:///{db_file}")
    assert db2.session_exists("p-1") is True
    history = db2.get_session_history("p-1")
    assert len(history) == 2
    assert history[0]["content"] == "Hello persistent world"
    assert history[1]["content"] == "Stored safely"
    assert history[1]["metadata"]["resolution_source"] == "LIVE_INFERENCE"
