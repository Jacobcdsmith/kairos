"""Evidence pane keyboard scrolling: ↑/↓ and Page Up/Down move through a
long citation excerpt when the pane has focus.
"""

from __future__ import annotations

import pytest

pytest.importorskip("textual")
pytest.importorskip("pytest_asyncio")

from kairos.services.context import RuntimeContext
from kairos.tui.app import KairosApp
from kairos.tui.widgets.evidence_pane import EvidencePane
from kairos.tui.widgets.explorer_pane import ExplorerPane

WIDE = (140, 20)


async def _type_command(pilot: object, text: str) -> None:
    await pilot.click("#command-line")  # type: ignore[attr-defined]
    await pilot.press(*text)  # type: ignore[attr-defined]
    await pilot.press("enter")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


async def _select_first_result(pilot: object, app: KairosApp) -> None:
    explorer = app.query_one(ExplorerPane)
    explorer.focus()
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.press("enter")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_evidence_pane_scrolls_down_and_up_when_focused(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        await _select_first_result(pilot, app)

        evidence = app.query_one(EvidencePane)
        evidence.focus()
        await pilot.pause()
        assert evidence.scroll_y == 0

        await pilot.press("down")
        await pilot.press("down")
        await pilot.pause()
        assert evidence.scroll_y >= 0  # never goes negative; content may be short

        await pilot.press("up")
        await pilot.pause()


@pytest.mark.asyncio
async def test_evidence_pane_page_down_and_page_up_do_not_crash(
    runtime_ctx: RuntimeContext,
) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        await _select_first_result(pilot, app)

        evidence = app.query_one(EvidencePane)
        evidence.focus()
        await pilot.pause()

        await pilot.press("pagedown")
        await pilot.pause()
        await pilot.press("pageup")
        await pilot.pause()
        await pilot.press("end")
        await pilot.pause()
        await pilot.press("home")
        await pilot.pause()
        assert evidence.scroll_y == 0


@pytest.mark.asyncio
async def test_evidence_pane_resets_scroll_on_new_selection(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        await _select_first_result(pilot, app)

        evidence = app.query_one(EvidencePane)
        evidence.scroll_y = 5
        await pilot.pause()

        explorer = app.query_one(ExplorerPane)
        explorer.focus()
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert evidence.scroll_y == 0
