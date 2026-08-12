from __future__ import annotations

from typing import cast

from textual.css.query import NoMatches
from textual.suggester import Suggester
from textual.widgets import Input, Static

from kairos.tui.commands import KNOWN_COMMAND_NAMES, hint_text

_PROMPT = "⬢"


class _CommandSuggester(Suggester):
    """Ghost-text completion for the command *name* only (e.g. ``:sear`` ->
    ``:search ``) — never guesses at arguments, and stays silent once a
    space has been typed since the rest is free-form.
    """

    def __init__(self) -> None:
        super().__init__(case_sensitive=False, use_cache=False)

    async def get_suggestion(self, value: str) -> str | None:
        if not value.startswith(":") or " " in value:
            return None
        prefix = value[1:]
        if not prefix:
            return None
        matches = sorted(name for name in KNOWN_COMMAND_NAMES if name.startswith(prefix))
        if len(matches) == 1 and matches[0] != prefix:
            return f":{matches[0]} "
        return None


class _CommandHistoryCursor:
    """Ephemeral ↑/↓ cursor over ``TuiState.command_history``. The history
    list itself lives in state (and on disk); this only tracks *where in
    it* the user has scrolled, plus the in-progress line they were typing
    before they started cycling, so pressing Down back past the newest
    entry restores it — same as a shell history search.
    """

    def __init__(self) -> None:
        self._index: int | None = None
        self._draft: str = ""

    def reset(self) -> None:
        self._index = None
        self._draft = ""

    def prev(self, entries: tuple[str, ...], current_value: str) -> str | None:
        if not entries:
            return None
        if self._index is None:
            self._draft = current_value
            self._index = len(entries) - 1
        elif self._index > 0:
            self._index -= 1
        else:
            return None
        return entries[self._index]

    def next(self, entries: tuple[str, ...]) -> str | None:
        if self._index is None:
            return None
        if self._index < len(entries) - 1:
            self._index += 1
            return entries[self._index]
        self._index = None
        return self._draft


class CommandLine(Input):
    BINDINGS = [
        ("up", "history_prev", "Previous command"),
        ("down", "history_next", "Next command"),
    ]

    def __init__(self) -> None:
        super().__init__(
            placeholder=f"{_PROMPT}  :search <term>   ? for help   ^P to find",
            id="command-line",
            suggester=_CommandSuggester(),
        )
        self._history = _CommandHistoryCursor()
        # Set right before a history nav action assigns `self.value`, so the
        # `Input.Changed` message that assignment posts (asynchronously —
        # see textual's Input._watch_value) can be recognized as an echo of
        # our own edit rather than the user typing, and skip resetting the
        # cursor it just moved.
        self._last_history_value: str | None = None

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        if event.value == self._last_history_value:
            self._last_history_value = None
        else:
            self._history.reset()
        self._update_hint(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        text = event.value.strip()
        self._history.reset()
        self._update_hint("")
        if not text:
            return
        self.value = ""
        self.app.run_command(text)  # type: ignore[attr-defined]

    def _history_entries(self) -> tuple[str, ...]:
        return cast("tuple[str, ...]", self.app.state.command_history)  # type: ignore[attr-defined]

    def action_history_prev(self) -> None:
        value = self._history.prev(self._history_entries(), self.value)
        if value is not None:
            self._last_history_value = value
            self.value = value
            self.action_end()

    def action_history_next(self) -> None:
        value = self._history.next(self._history_entries())
        if value is not None:
            self._last_history_value = value
            self.value = value
            self.action_end()

    def _update_hint(self, value: str) -> None:
        try:
            hint = self.screen.query_one("#command-hint", Static)
        except NoMatches:
            return
        hint.update(hint_text(value))
