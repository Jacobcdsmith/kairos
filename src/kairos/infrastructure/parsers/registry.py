"""Parser lookup: extension first, then content sniffing for extension-less files."""

from __future__ import annotations

from pathlib import Path

from kairos.domain.errors import NoParserAvailableError
from kairos.domain.parser import Parser
from kairos.infrastructure.parsers.json_parser import JsonParser
from kairos.infrastructure.parsers.kconfig import KconfigParser
from kairos.infrastructure.parsers.logs import LogParser
from kairos.infrastructure.parsers.pdf import PdfParser
from kairos.infrastructure.parsers.repository_files import PythonParser
from kairos.infrastructure.parsers.text_markdown import MarkdownParser, TextParser


def default_parsers() -> list[Parser]:
    """Parsers in priority order. KconfigParser must precede JsonParser:
    both accept ``.json``, and Kconfig menu documents are also valid JSON —
    its ``sniff`` is the more specific check and must win first.
    """
    return [
        MarkdownParser(),
        TextParser(),
        KconfigParser(),
        JsonParser(),
        LogParser(),
        PythonParser(),
        PdfParser(),
    ]


class ParserRegistry:
    def __init__(self, parsers: list[Parser] | None = None) -> None:
        self._parsers = parsers if parsers is not None else default_parsers()

    def resolve(self, path: Path) -> Parser:
        for parser in self._parsers:
            if parser.sniff(path):
                return parser
        raise NoParserAvailableError(f"No parser can handle: {path}")
