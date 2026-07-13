"""Recursive JSON value type, shared by the JSON and Kconfig-menu-JSON parsers."""

from __future__ import annotations

type JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
