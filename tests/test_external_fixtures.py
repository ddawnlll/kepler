"""Harici fixture tamamen yoksa açık skip; kısmi veya bozuk dataset test kapısını kırar."""
import pytest

from tests import test_indicators as indicators


def test_missing_external_dataset_is_an_explicit_skip(tmp_path, monkeypatch):
    monkeypatch.setattr(indicators, "TVDIR", tmp_path / "absent")
    with pytest.raises(pytest.skip.Exception, match="Harici TradingView fixture yok"):
        indicators.tv_case("1d")


def test_partial_external_dataset_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(indicators, "TVDIR", tmp_path)
    (tmp_path / "tv_1d.json").write_text('{"values": {}}')
    with pytest.raises(FileNotFoundError, match="Eksik TradingView fixture"):
        indicators.tv_case("1d")
