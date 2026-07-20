from __future__ import annotations

from textual.widgets import Input

_PROMPT = "\u2b22"


class CommandLine(Input):
    def __init__(self) -> None:
        super().__init__(
            placeholder=f"{_PROMPT}  :search <term>   ? for help   ^P to find",
            id="command-line",
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        text = event.value.strip()
        if not text:
            return
        self.value = ""
        self.app.run_command(text)  # type: ignore[attr-defined]
