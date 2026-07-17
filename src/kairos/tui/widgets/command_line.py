"""The persistent command line: an ``Input`` that submits ``:command`` text
to the app's dispatcher and clears itself. This is the whole "conversation"
surface — it never becomes a chat box; it only ever accepts grammar
``commands.py`` can parse.
"""

from __future__ import annotations

from textual.widgets import Input


class CommandLine(Input):
    def __init__(self) -> None:
        super().__init__(placeholder=":search <term>   ?  for help", id="command-line")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        text = event.value.strip()
        if not text:
            return
        self.value = ""
        self.app.run_command(text)  # type: ignore[attr-defined]
