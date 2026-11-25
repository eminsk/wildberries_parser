"""
Tests for Unified Free & Paid AI Engine (`wb_parser.ai`), CLI `ai`, MCP `wb_ai_providers`,
and SmartReviewAnalyzer free/local/paid LLM routing.
"""

from __future__ import annotations

import json
import types
from pathlib import Path
from typing import Any, Dict

import wb_parser.ai as wb_ai
from wb_parser.cli import main as cli_main
from wb_parser.client import WBClient
from wb_parser.mcp_server import WBMCPServer
from wb_parser.reviews import ReviewItem, ReviewSummary, SmartReviewAnalyzer


def test_list_and_find_preset_ai_providers(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(wb_ai, "is_g4f_available", lambda: False)
    monkeypatch.setattr(wb_ai, "_load_g4f_modules", lambda: None)

    all_providers = wb_ai.list_ai_providers()
    ids = {p.id for p in all_providers}
    assert {"openai", "deepseek", "openrouter", "proxyapi", "groq", "gemini", "ollama", "lmstudio"}.issubset(ids)

    local_only = wb_ai.list_ai_providers(only_free=True)
    assert all(not p.needs_auth for p in local_only)
    assert any(p.id == "ollama" for p in local_only)

    ds = wb_ai.find_ai_provider("deepseek", all_providers)
    assert ds is not None
    assert ds.base_url == "https://api.deepseek.com/v1"
    assert ds.configured is False

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-ds")
    ds_configured = wb_ai.find_ai_provider("deepseek", wb_ai.list_ai_providers())
    assert ds_configured is not None and ds_configured.configured is True


def test_mock_g4f_discovery_fallback_and_health_diagnostics(monkeypatch):
    class BrokenFreeProvider:
        working = True
        needs_auth = False
        supports_stream = True
        default_model = "broken-model"
        models = ["broken-model"]
        url = "https://broken.example"

    class WorkingFreeProvider:
        working = True
        needs_auth = False
        supports_stream = True
        default_model = "openai-fast"
        models = ["openai-fast", "mistral"]
        url = "https://airforce.example"

    class SecretPaidG4F:
        working = True
        needs_auth = True
        supports_stream = False
        default_model = "secret"
        url = "https://paid.example"

    BrokenFreeProvider.__name__ = "Yqcloud"      # Candidate #1 in FREE_G4F_CANDIDATES
    WorkingFreeProvider.__name__ = "Airforce"     # Candidate #2 (fallback target)

    fake_providers_ns = types.SimpleNamespace(
        __providers__=[BrokenFreeProvider, WorkingFreeProvider, SecretPaidG4F],
        Yqcloud=BrokenFreeProvider,
        Airforce=WorkingFreeProvider,
        SecretPaidG4F=SecretPaidG4F,
    )

    class _FakeCompletions:
        def __init__(self, provider_cls):
            self.provider_cls = provider_cls

        def create(self, model="", messages=None, stream=False):
            if self.provider_cls is BrokenFreeProvider:
                raise RuntimeError("HTTP 403 Cloudflare blocked")
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='{"plus": ["Удобные"], "minus": ["Нет"]}'))]
            )

    class _FakeG4FClient:
        def __init__(self, provider=None):
            self.chat = types.SimpleNamespace(completions=_FakeCompletions(provider))

    monkeypatch.setattr(wb_ai, "_load_g4f_modules", lambda: (fake_providers_ns, _FakeG4FClient))

    free_list = wb_ai.list_g4f_providers(only_working=True, only_free=True)
    assert [p.id for p in free_list] == ["Yqcloud", "Airforce"]

    # Auto-fallback skips Yqcloud (403) and succeeds on Airforce
    chat_res = wb_ai.generate_completion("Test prompt", mode="free")
    assert chat_res.ok is True
    assert chat_res.provider == "Airforce"
    assert chat_res.tier == "free"
    assert "g4f:Airforce/openai-fast" in chat_res.attempts
    assert any("Yqcloud" in a for a in chat_res.attempts)

    # Direct health-check classifies 403 Cloudflare cleanly
    fail_health = wb_ai.test_ai_provider("Yqcloud", mode="free")
    assert fail_health.success is False
    assert fail_health.hint and "Cloudflare" in fail_health.hint


def test_paid_and_local_openai_compat_routing(monkeypatch):
    calls = []

    def _fake_post(prompt: str, *, base_url: str, api_key: str, model: str, temperature: float = 0.2, timeout: float = 25.0) -> str:
        calls.append({"base_url": base_url, "api_key": api_key, "model": model})
        return '{"plus": ["Быстрая доставка"], "minus": ["Маломерят"]}'

    monkeypatch.setattr(wb_ai, "_post_openai_chat", _fake_post)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-999")

    # Paid preset auto-resolves DeepSeek URL, model, and env key
    paid = wb_ai.generate_completion("Analyze", mode="paid", provider="deepseek")
    assert paid.ok is True
    assert paid.tier == "paid"
    assert paid.provider == "deepseek"
    assert calls[-1]["base_url"] == "https://api.deepseek.com/v1"
    assert calls[-1]["api_key"] == "sk-ds-999"
    assert calls[-1]["model"] == "deepseek-chat"

    # Local Ollama needs NO API key
    local = wb_ai.generate_completion("Analyze", mode="local", provider="ollama", model="qwen2.5")
    assert local.ok is True
    assert local.tier == "local"
    assert calls[-1]["base_url"] == "http://localhost:11434/v1"
    assert calls[-1]["api_key"] == "ollama"
    assert calls[-1]["model"] == "qwen2.5"

    # Missing key in paid mode fails cleanly
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("WB_AI_KEY", raising=False)
    missing = wb_ai.generate_completion("Analyze", mode="paid", provider="openai")
    assert missing.ok is False
    assert "Missing API key" in (missing.error or "")


def test_reviews_summary_with_free_and_paid_ai(monkeypatch):
    client = WBClient()
    analyzer = SmartReviewAnalyzer(client)
    summary = ReviewSummary(
        nm_id=141217830,
        root_id=181851928,
        product_name="Кроссовки",
        top_pros=["Легкие"],
        top_cons=["Жмут"],
        reviews=[ReviewItem(rating=5, pros="Легкие", text="Супер")],
        summary_mode="offline",
    )

    monkeypatch.setattr(
        "wb_parser.reviews.generate_completion",
        lambda prompt, **kw: wb_ai.AIChatResult(
            ok=True,
            content='{"plus": ["Очень легкие", "Хорошая подошва"], "minus": ["Трудно мыть"]}',
            provider=kw.get("provider") or "Pollinations",
            model=kw.get("model") or "gpt-4o-mini",
            backend="g4f",
            tier=kw.get("mode") or "free",
        ),
    )

    res = analyzer.summarize_with_llm(summary, mode="free", provider="Pollinations")
    assert res.ai_provider == "Pollinations"
    assert res.top_pros == ["Очень легкие", "Хорошая подошва"]
    assert res.top_cons == ["Трудно мыть"]
    assert res.summary_mode == "free:Pollinations/gpt-4o-mini"


def test_cli_ai_subcommand_json(capsys, monkeypatch):
    monkeypatch.setattr(wb_ai, "_load_g4f_modules", lambda: None)
    monkeypatch.setattr(wb_ai, "_post_openai_chat", lambda *a, **kw: "Работает")

    rc_list = cli_main(["ai", "--list", "--tier", "paid", "--json"])
    assert rc_list == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] >= 4
    assert any(p["id"] == "deepseek" for p in payload["providers"])

    rc_test = cli_main(["ai", "-p", "ollama", "--test", "--mode", "local", "--json"])
    assert rc_test == 0
    test_payload = json.loads(capsys.readouterr().out)
    assert test_payload["success"] is True
    assert test_payload["provider"] == "ollama"


def test_mcp_ai_providers_tool(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(wb_ai, "_load_g4f_modules", lambda: None)
    monkeypatch.setattr(wb_ai, "_post_openai_chat", lambda *a, **kw: "ОК")

    srv = WBMCPServer(tracker_db=str(tmp_path / "ai_mcp.db"))
    list_resp = srv.handle_request({
        "jsonrpc": "2.0",
        "id": 100,
        "method": "tools/call",
        "params": {"name": "wb_ai_providers", "arguments": {"action": "list", "tier": "local"}},
    })
    sc = list_resp["result"]["structuredContent"]
    assert sc["count"] == 2
    assert {p["id"] for p in sc["providers"]} == {"ollama", "lmstudio"}

    chat_resp = srv.handle_request({
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tools/call",
        "params": {"name": "wb_ai_providers", "arguments": {"action": "chat", "mode": "local", "provider": "ollama", "prompt": "hi"}},
    })
    assert chat_resp["result"]["structuredContent"]["ok"] is True
    assert chat_resp["result"]["structuredContent"]["content"] == "ОК"


def test_ollama_env_url_g4f_prefix_and_nag_filter(monkeypatch):
    seen_urls = []

    def _fake_post(prompt: str, *, base_url: str, api_key: str, model: str, temperature: float = 0.2, timeout: float = 25.0) -> str:
        seen_urls.append(base_url)
        return "Local OK"

    monkeypatch.setattr(wb_ai, "_post_openai_chat", _fake_post)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11500/v1")
    local_res = wb_ai.generate_completion("ping", mode="local", provider="ollama")
    assert local_res.ok is True
    assert seen_urls[-1] == "http://127.0.0.1:11500/v1"

    class _NagGemini:
        working = True
        needs_auth = False
        default_model = "gemini-free"

    _NagGemini.__name__ = "Gemini"
    fake_ns = types.SimpleNamespace(__providers__=[_NagGemini], Gemini=_NagGemini)

    class _NagCompletions:
        def create(self, model="", messages=None, stream=False):
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="Sign up and repeat your request."))]
            )

    class _NagClient:
        def __init__(self, provider=None):
            self.chat = types.SimpleNamespace(completions=_NagCompletions())

    monkeypatch.setattr(wb_ai, "_load_g4f_modules", lambda: (fake_ns, _NagClient))
    # `g4f:Gemini` explicitly routes to g4f instead of Google API preset and filters nag text
    g4f_res = wb_ai.generate_completion("ping", mode="auto", provider="g4f:Gemini")
    assert g4f_res.backend == "g4f"
    assert g4f_res.ok is False
    assert "non-text or signup prompt" in (g4f_res.error or "")
