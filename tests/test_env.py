import sys
from importlib.metadata import version


def test_python_312():
    assert sys.version_info[:2] == (3, 12)


def test_pinned_engines():
    assert version("nautilus_trader") == "2.0.0rc5"
    assert version("vectorbt") == "1.1.1"


def test_engines_import():
    import duckdb  # noqa: F401
    from nautilus_trader.backtest import BacktestEngine  # noqa: F401
    import vectorbt  # noqa: F401
