"""Explorer pane polish: item-count title, scroll indicators, line-number
gutter, search-term highlighting, and Ctrl+G "go to item".
"""

from __future__ import annotations

import pytest

pytest.importorskip("textual")
pytest.importorskip("pytest_asyncio")

from kairos.services.context import RuntimeContext
from kairos.tui.app import KairosApp
from kairos.tui.widgets.explorer_pane import ExplorerPane, highlighted

WIDE = (140, 40)


async def _type_command(pilot: object, text: str) -> None:
    await pilot.click("#command-line")  # type: ignore[attr-defined]
    await pilot.press(*text)  # type: ignore[attr-defined]
    await pilot.press("enter")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


def test_highlighted_wraps_case_insensitive_match() -> None:
    result = highlighted("The Widget Manual", "widget")
    assert "[reverse]Widget[/reverse]" in result


def test_highlighted_escapes_when_no_match() -> None:
    assert highlighted("plain text", "nope") == "plain text"


def test_highlighted_handles_empty_term() -> None:
    assert highlighted("plain text", None) == "plain text"
    assert highlighted("plain text", "") == "plain text"


@pytest.mark.asyncio
async def test_explorer_border_title_shows_mode_and_count(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        explorer = app.query_one(ExplorerPane)
        assert explorer.border_title == "Artifacts (7)"


@pytest.mark.asyncio
async def test_explorer_rows_carry_line_number_gutter_every_fifth(
    runtime_ctx: RuntimeContext,
) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        explorer = app.query_one(ExplorerPane)
        rows = list(explorer.children)
        assert len(rows) == 7
        fifth_row_text = str(rows[4].children[0].renderable)  # type: ignore[attr-defined]
        assert fifth_row_text.startswith("   5 ")


@pytest.mark.asyncio
async def test_trace_nodes_highlight_the_query_term(runtime_ctx: RuntimeContext) -> None:
    # :trace's node labels are the entity/span text itself (unlike :search's
    # rows, which only show the source path) — so this is where the query
    # term actually shows up in the Explorer list for highlighting to matter.
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":trace widget")
        explorer = app.query_one(ExplorerPane)
        rows = list(explorer.children)
        assert rows
        any_highlighted = any(
            "[reverse]" in str(row.children[0].renderable)  # type: ignore[attr-defined]
            for row in rows
        )
        assert any_highlighted


@pytest.mark.asyncio
async def test_ctrl_g_jumps_to_requested_item(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        explorer = app.query_one(ExplorerPane)
        explorer.focus()
        await pilot.pause()

        await pilot.press("ctrl+g")
        await pilot.pause()
        await pilot.press("3")
        await pilot.press("enter")
        await pilot.pause()

        assert explorer.index == 2


@pytest.mark.asyncio
async def test_ctrl_g_cancel_leaves_index_unchanged(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        explorer = app.query_one(ExplorerPane)
        explorer.focus()
        await pilot.pause()
        original_index = explorer.index

        await pilot.press("ctrl+g")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert explorer.index == original_index
