"""The help overlay: command grammar, keybindings, provenance legend, and
the local-only/read-only boundary statement. Closed with Escape or ``?``.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

_HELP_TEXT = """\
 KAIROS Terminal Lineage Interface

 COMMANDS
   :home                       recent local activity
   :artifacts [kind]           list ingested artifacts
   :search <query>             full-text search (alias: :s)
   :show <artifact-id> [loc]   structured source detail
   :trace <term-or-id>         explicit-relation traversal (alias: :t)
   :well list                  all coherence wells
   :well use <name>            set the active well (context filter)
   :well clear                 clear the active well
   :well show <name>           one well's members
   :config <symbol>            Kconfig symbol lookup
   :logs <query>               log search with locators
   :doctor                     workspace health checks
   :ingest [path] [-r]         ingest files (default: workspace root)
   :history                    this session's command log
   :help  (or bare ?)          this screen
   :refresh  (or r)            re-run the last successful command
   :quit  (or :q)              quit

 KEYBINDINGS
   Ctrl+P   fuzzy finder            Tab / Shift+Tab   cycle pane focus
   Ctrl+R   history search          /                 start a search
   Enter    run / inspect           w                 well selector
   Up/Down  move selection          c                 copy citation
   r        re-run last command     y                 copy excerpt
   t        interactive tutorial    ?                 help
   Escape   close overlay           q                 quit (not while typing)

 PROVENANCE LAYERS
   RAW        the ingested bytes themselves
   EXTRACTED  deterministic parser output (a span, an entity)
   DERIVED    a machine-made link between already-extracted objects
   USER       owner-authored (a note, a well membership)

 Every result carries a full citation: artifact id, source path, exact
 locator, parser + version, and one of the four layers above. Trace edges
 marked DERIVED are explicit deterministic rule matches — never a
 semantic-similarity or embedding-based claim.

 LOCAL / READ-ONLY
   No network access. No telemetry. No LLM, no embeddings. This interface
   cannot edit, delete, or move any registered source file. The only writes
   it can make are: adding a note, activating/clearing a well, and ingesting.

 Press Escape to close.
"""


class HelpScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close"), ("question_mark", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            yield Static(_HELP_TEXT, id="help-text")
