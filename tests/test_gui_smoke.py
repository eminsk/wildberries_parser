"""
GUI import, configuration persistence, and window smoke checks.
"""

from __future__ import annotations

from pathlib import Path

from wb_parser.gui.app import WBGUIConfig


def test_gui_config_persistence(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "gui_config.json"
    monkeypatch.setattr(WBGUIConfig, "CONFIG_PATH", cfg_file)

    cfg = WBGUIConfig()
    cfg.min_price = "1500"
    cfg.dest_name = "Казань"
    cfg.save()
    assert cfg_file.exists()

    loaded = WBGUIConfig.load()
    assert loaded.min_price == "1500"
    assert loaded.dest_name == "Казань"


def test_gui_module_imports():
    import wb_parser.gui as gui_pkg
    assert callable(gui_pkg.main_gui)


def test_gui_missing_customtkinter_returns_nonzero(monkeypatch, capsys):
    import wb_parser.gui as gui_pkg
    import wb_parser.gui.app as gui_app

    monkeypatch.setattr(gui_app, "ctk", None)
    rc = gui_pkg.main_gui()
    assert rc == 1
    assert "wb-sdk-pro[gui]" in capsys.readouterr().err


def test_mobileproxy_donate_and_assets():
    from wb_parser import (
        DONATE_TRONSCAN_URL,
        DONATE_USDT_TRC20,
        MOBILEPROXY_FREE_TRIAL_URL,
        MOBILEPROXY_REFERRAL_URL,
        WBClient,
        resolve_proxy_change_url,
    )
    from wb_parser.gui.app import _resolve_asset

    assert "279117" in MOBILEPROXY_REFERRAL_URL
    assert "free" in MOBILEPROXY_FREE_TRIAL_URL
    assert DONATE_USDT_TRC20.startswith("T")
    assert DONATE_USDT_TRC20 in DONATE_TRONSCAN_URL
    assert resolve_proxy_change_url(None, "abc123") == "https://changeip.mobileproxy.space/?proxy_key=abc123&format=json"

    with WBClient(mobileproxy_key="key999") as c:
        assert c.transport.proxy_change_url == "https://changeip.mobileproxy.space/?proxy_key=key999&format=json"

    assert _resolve_asset("icon.ico") is not None
    assert _resolve_asset("icon.png") is not None
