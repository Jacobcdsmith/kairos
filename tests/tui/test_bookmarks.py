"""Bookmarks: JSON persistence roundtrip (services/bookmarks.py), the
``:bookmark``/``:bookmarks`` command grammar, and the Shift+B quick-access
picker end to end.
"""

from __future__ import annotations

import pytest

from kairos.domain.errors import BookmarkNotFoundError, KairosError
from kairos.schemas.bookmark import BookmarkResult
from kairos.services.bookmarks import (
    bookmarks_file_path,
    list_bookmarks,
    remove_bookmark,
    save_bookmark,
)
from kairos.services.context import RuntimeContext
from kairos.tui.controller import dispatch_text
from kairos.tui.state import TuiState, as_list_of


def _fresh_state(runtime_ctx: RuntimeContext) -> TuiState:
    return TuiState(workspace_path=runtime_ctx.workspace.root)


# ── services/bookmarks.py — pure persistence ────────────────────────────


def test_bookmarks_roundtrip_save_and_list(runtime_ctx: RuntimeContext) -> None:
    assert list_bookmarks(runtime_ctx) == []

    save_bookmark(runtime_ctx, "widgets", ":search widget")
    save_bookmark(runtime_ctx, "wells", ":well list")

    bookmarks = list_bookmarks(runtime_ctx)
    assert [b.name for b in bookmarks] == ["widgets", "wells"]
    assert [b.command for b in bookmarks] == [":search widget", ":well list"]
    assert bookmarks_file_path(runtime_ctx.workspace.root).exists()


def test_saving_an_existing_name_overwrites_and_moves_to_end(runtime_ctx: RuntimeContext) -> None:
    save_bookmark(runtime_ctx, "widgets", ":search widget")
    save_bookmark(runtime_ctx, "wells", ":well list")
    save_bookmark(runtime_ctx, "widgets", ":search widgets --limit 5")

    bookmarks = list_bookmarks(runtime_ctx)
    assert [b.name for b in bookmarks] == ["wells", "widgets"]
    assert bookmarks[-1].command == ":search widgets --limit 5"


def test_remove_bookmark(runtime_ctx: RuntimeContext) -> None:
    save_bookmark(runtime_ctx, "widgets", ":search widget")
    remove_bookmark(runtime_ctx, "widgets")
    assert list_bookmarks(runtime_ctx) == []


def test_remove_unknown_bookmark_is_actionable_error(runtime_ctx: RuntimeContext) -> None:
    with pytest.raises(BookmarkNotFoundError):
        remove_bookmark(runtime_ctx, "nope")


def test_list_bookmarks_on_missing_file_is_empty(runtime_ctx: RuntimeContext) -> None:
    assert list_bookmarks(runtime_ctx) == []


def test_list_bookmarks_raises_actionable_error_on_corrupt_file(
    runtime_ctx: RuntimeContext,
) -> None:
    bookmarks_file_path(runtime_ctx.workspace.root).write_text("not json", encoding="utf-8")
    with pytest.raises(KairosError):
        list_bookmarks(runtime_ctx)


# ── controller: :bookmark / :bookmarks command grammar ──────────────────


def test_bookmark_command_saves_the_last_successful_command(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":search widget")
    state = dispatch_text(runtime_ctx, state, ":bookmark widgets")

    assert state.mode == "bookmarks"
    assert state.status == "idle"
    bookmarks = as_list_of(state.last_result, BookmarkResult)
    assert bookmarks is not None
    assert bookmarks[0].name == "widgets"
    assert bookmarks[0].command == ":search widget"
    assert state.recent_bookmarks[-1].name == "widgets"


def test_bookmark_with_nothing_run_yet_is_actionable_error(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":bookmark widgets")
    assert state.status == "error"
    assert "Nothing to bookmark" in (state.status_message or "")


def test_bookmark_without_a_name_is_a_usage_error(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":search widget")
    state = dispatch_text(runtime_ctx, state, ":bookmark")
    assert state.status == "error"
    assert "Usage" in (state.status_message or "")


def test_bookmarks_command_lists_saved_bookmarks(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":search widget")
    state = dispatch_text(runtime_ctx, state, ":bookmark widgets")
    state = dispatch_text(runtime_ctx, state, ":artifacts")
    state = dispatch_text(runtime_ctx, state, ":bookmark all-artifacts")

    state = dispatch_text(runtime_ctx, state, ":bookmarks")
    assert state.mode == "bookmarks"
    assert "2 bookmark" in (state.status_message or "")
    names = [b.name for b in state.recent_bookmarks]
    assert names == ["widgets", "all-artifacts"]


def test_bookmark_remove_via_command(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":search widget")
    state = dispatch_text(runtime_ctx, state, ":bookmark widgets")
    state = dispatch_text(runtime_ctx, state, ":bookmark --remove widgets")

    assert state.status == "idle"
    assert list_bookmarks(runtime_ctx) == []
    assert state.recent_bookmarks == ()


def test_bookmark_remove_unknown_name_is_actionable_error(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":bookmark --remove nope")
    assert state.status == "error"
    assert "nope" in (state.status_message or "")


def test_recent_bookmarks_caps_at_three(runtime_ctx: RuntimeContext) -> None:
    state = _fresh_state(runtime_ctx)
    for name in ("a", "b", "c", "d"):
        state = dispatch_text(runtime_ctx, state, ":search widget")
        state = dispatch_text(runtime_ctx, state, f":bookmark {name}")

    assert [b.name for b in state.recent_bookmarks] == ["b", "c", "d"]
    assert [b.name for b in list_bookmarks(runtime_ctx)] == ["a", "b", "c", "d"]


# ── Pilot-driven: Shift+B picker, tab bar ────────────────────────────────

pytest.importorskip("textual")
pytest.importorskip("pytest_asyncio")

from kairos.schemas.search import SearchResult  # noqa: E402
from kairos.tui.app import KairosApp  # noqa: E402
from kairos.tui.screens.bookmark_picker import BookmarkPickerScreen  # noqa: E402
from kairos.tui.widgets.explorer_pane import ExplorerPane  # noqa: E402
from kairos.tui.widgets.tab_bar import TabBar  # noqa: E402

WIDE = (140, 30)


async def _type_command(pilot: object, text: str) -> None:
    await pilot.click("#command-line")  # type: ignore[attr-defined]
    await pilot.press(*text)  # type: ignore[attr-defined]
    await pilot.press("enter")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_shift_b_opens_picker_and_running_a_bookmark_reruns_its_command(
    runtime_ctx: RuntimeContext,
) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":search widget")
        await _type_command(pilot, ":bookmark widgets")
        await _type_command(pilot, ":artifacts")
        assert app.state.mode == "artifacts"

        app.query_one(ExplorerPane).focus()  # command-line still holds focus otherwise
        await pilot.pause()
        await pilot.press("B")
        await pilot.pause()
        assert isinstance(app.screen, BookmarkPickerScreen)

        await pilot.press("enter")
        await pilot.pause()

        assert not isinstance(app.screen, BookmarkPickerScreen)
        assert app.state.mode == "search"
        assert isinstance(app.state.last_result, SearchResult)


@pytest.mark.asyncio
async def test_bookmark_picker_escape_cancels_without_running_anything(
    runtime_ctx: RuntimeContext,
) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":search widget")
        await _type_command(pilot, ":bookmark widgets")
        await _type_command(pilot, ":artifacts")

        app.query_one(ExplorerPane).focus()
        await pilot.pause()
        await pilot.press("B")
        await pilot.pause()
        assert isinstance(app.screen, BookmarkPickerScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, BookmarkPickerScreen)
        assert app.state.mode == "artifacts"


@pytest.mark.asyncio
async def test_bookmark_picker_d_removes_and_syncs_tab_bar(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":search widget")
        await _type_command(pilot, ":bookmark widgets")
        assert any(
            t.mode == "bookmarks"  # type: ignore[attr-defined]
            for t in app.query_one(TabBar).children[1:]
        )

        app.query_one(ExplorerPane).focus()
        await pilot.pause()
        await pilot.press("B")
        await pilot.pause()
        assert isinstance(app.screen, BookmarkPickerScreen)
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert list_bookmarks(runtime_ctx) == []
        assert app.state.recent_bookmarks == ()
        assert len(list(app.query_one(TabBar).children)) == 1


@pytest.mark.asyncio
async def test_tab_bar_shows_up_to_three_most_recent_bookmarks(
    runtime_ctx: RuntimeContext,
) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        for name in ("a", "b", "c", "d"):
            await _type_command(pilot, ":search widget")
            await _type_command(pilot, f":bookmark {name}")

        tab_labels = [
            str(t.renderable)  # type: ignore[attr-defined]
            for t in app.query_one(TabBar).children
        ]
        assert "★ d" in tab_labels
        assert "★ c" in tab_labels
        assert "★ b" in tab_labels
        assert "★ a" not in tab_labels
