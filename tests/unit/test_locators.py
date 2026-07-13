"""Locator string round-tripping and JSON serialization."""

from __future__ import annotations

import pytest

from kairos.domain.errors import InvalidLocatorError
from kairos.domain.locators import (
    JsonPathLocator,
    KconfigSymbolLocator,
    LineRangeLocator,
    Locator,
    LogEventLocator,
    PdfPageLocator,
    RepoFileLinesLocator,
    locator_from_json,
    locator_to_json,
    parse_locator_str,
)

LOCATORS: list[Locator] = [
    PdfPageLocator(page=3),
    LineRangeLocator(start_line=10, end_line=14),
    JsonPathLocator(json_path="$.a.b[2]"),
    KconfigSymbolLocator(menu_path="Main/Networking/CONFIG_WIFI"),
    RepoFileLinesLocator(file_path="src/foo.py", start_line=10, end_line=14),
    LogEventLocator(line_number=42, timestamp="2024-01-01T00:00:00Z"),
    LogEventLocator(line_number=1, timestamp=None),
]


@pytest.mark.parametrize("locator", LOCATORS)
def test_string_round_trip(locator: Locator) -> None:
    text = locator.to_str()
    assert parse_locator_str(text) == locator


@pytest.mark.parametrize("locator", LOCATORS)
def test_json_round_trip(locator: Locator) -> None:
    data = locator_to_json(locator)
    assert locator_from_json(data) == locator


def test_invalid_locator_string_raises() -> None:
    with pytest.raises(InvalidLocatorError):
        parse_locator_str("not-a-locator")
