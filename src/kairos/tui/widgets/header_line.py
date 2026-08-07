from __future__ import annotations

from rich.markup import escape
from textual.widgets import Static

from kairos.tui.state import TuiState

_GLYPH = "⬢"
_WELL_GLYPH = "◈"
_OFFLINE_GLYPH = "●"


def _format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


class HeaderLine(Static):
    def __init__(self) -> None:
        super().__init__(id="header-line")

    def refresh_from_state(self, state: TuiState) -> None:
        workspace_name = escape(state.workspace_path.name)
        well = escape(state.active_well) if state.active_well else "none"
        stats = (
            f"{state.artifact_count} artifact(s) · "
            f"{_format_size(state.workspace_size_bytes)} · "
            f"{state.well_count} well(s)"
        )
        runtime = ""
        if state.last_command_label is not None and state.last_command_ms is not None:
            runtime = f"  │  {state.last_command_label} took {state.last_command_ms}ms"
        self.update(
            f" {_GLYPH} KAIROS  │  ws: {workspace_name}  "
            f"│  {_WELL_GLYPH} well: {well}  │  {stats}"
            f"{runtime}  │  {_OFFLINE_GLYPH} LOCAL"
        )
