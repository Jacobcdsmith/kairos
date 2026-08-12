"""Header/status line: active well, workspace stats, and last-command
runtime shown in the header; color-coded success/error in the status line.
"""

from __future__ import annotations

import pytest

pytest.importorskip("textual")
pytest.importorskip("pytest_asyncio")

from kairos.services.context import RuntimeContext
from kairos.tui.app import KairosApp
from kairos.tui.widgets.header_line import HeaderLine, format_size
from kairos.tui.widgets.status_line import StatusLine

WIDE = (160, 40)


async def _type_command(pilot: object, text: str) -> None:
    await pilot.click("#command-line")  # type: ignore[attr-defined]
    await pilot.press(*text)  # type: ignore[attr-defined]
    await pilot.press("enter")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


def test_format_size_units() -> None:
    assert format_size(0) == "0B"
    assert format_size(512) == "512B"
    assert format_size(2048) == "2.0KB"
    assert format_size(5 * 1024 * 1024) == "5.0MB"


@pytest.mark.asyncio
async def test_header_shows_workspace_stats_and_runtime(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":home")
        header_text = str(app.query_one(HeaderLine).renderable)
        assert "7 artifact(s)" in header_text
        assert "well(s)" in header_text
        assert "home took" in header_text
        assert "ms" in header_text


@pytest.mark.asyncio
async def test_header_reflects_active_well(runtime_ctx: RuntimeContext) -> None:
    from kairos.services.wells import create_well

    create_well(runtime_ctx, "docs", "just docs")
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":well use docs")
        header_text = str(app.query_one(HeaderLine).renderable)
        assert "well: docs" in header_text


@pytest.mark.asyncio
async def test_status_line_colors_success_and_error(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        # Static's `.update()` stores a Rich renderable; render it to plain
        # segments to check markup was actually applied, not just present as
        # literal text.
        status = app.query_one(StatusLine)
        from rich.console import Console

        console = Console(record=True, width=120, force_terminal=True, color_system="standard")
        console.print(status.renderable)
        rendered = console.export_text(styles=True)
        assert "\x1b[32m" in rendered  # green

        await _type_command(pilot, ":bogus")
        console = Console(record=True, width=120, force_terminal=True, color_system="standard")
        console.print(status.renderable)
        rendered = console.export_text(styles=True)
        assert "\x1b[31m" in rendered  # red


@pytest.mark.asyncio
async def test_status_line_shows_running_before_dispatch_completes(
    runtime_ctx: RuntimeContext,
) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await pilot.pause()
        status = app.query_one(StatusLine)
        status.show_running(":doctor")
        text = str(status.renderable)
        assert "running" in text
        assert ":doctor" in text
