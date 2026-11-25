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
