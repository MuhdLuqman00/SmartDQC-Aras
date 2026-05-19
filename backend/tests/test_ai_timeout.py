"""The schema-mapping LLM call must be bounded so a cold/slow Ollama can't
hang /upload/preview past the nginx gateway timeout (the 504 -> "check file
format" bug). generate() takes an optional timeout; ai_suggest_mapping passes
a short one so its existing graceful fallback fires fast.
"""
import backend.ai.ollama_client as oc
import backend.ai.schema_mapper as sm


class _FakeResp:
    status_code = 200

    def json(self):
        return {"response": "{}"}


def test_generate_accepts_custom_timeout(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["timeout"] = timeout
        return _FakeResp()

    monkeypatch.setattr(oc.httpx, "post", fake_post)
    oc.generate("hi", timeout=15.0)
    assert captured["timeout"] == 15.0


def test_generate_default_timeout_unchanged(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["timeout"] = timeout
        return _FakeResp()

    monkeypatch.setattr(oc.httpx, "post", fake_post)
    oc.generate("hi")
    assert captured["timeout"] == 300.0


def test_ai_suggest_mapping_uses_short_bounded_timeout(monkeypatch):
    captured = {}

    def fake_generate(prompt, system=None, json_mode=False, timeout=None):
        captured["timeout"] = timeout
        return "{}"

    monkeypatch.setattr(sm, "generate", fake_generate)
    sm.ai_suggest_mapping(["col1"], {"col1": ["a"]}, "unknown")
    assert captured["timeout"] is not None
    assert captured["timeout"] <= 30
