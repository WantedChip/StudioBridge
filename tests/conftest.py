"""StudioBridge master pytest configuration and root fixtures."""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add command line options for live testing."""
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run live tests that require an active FL Studio instance",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "winmm: mark test as requiring the Windows Multimedia API (winmm.dll)"
    )
    config.addinivalue_line("markers", "live: mark test as requiring an active FL Studio instance")
    config.addinivalue_line(
        "markers", "emulator: mark test as executing inside the controller script emulator"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Modify test collection to skip live or platform-specific tests when appropriate."""
    run_live = config.getoption("--run-live", default=False)
    markexpr = config.getoption("-m", default="")

    # Skip live tests by default unless explicitly requested
    has_live_mark = isinstance(markexpr, str) and "live" in markexpr
    if not run_live and not has_live_mark:
        skip_live = pytest.mark.skip(
            reason="live test skipped by default (pass --run-live or -m live)"
        )
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip_live)

    # Skip winmm tests on non-Windows platforms
    if sys.platform != "win32":
        skip_winmm = pytest.mark.skip(reason="winmm tests require Windows platform")
        for item in items:
            if "winmm" in item.keywords:
                item.add_marker(skip_winmm)
