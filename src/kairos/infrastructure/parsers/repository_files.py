"""Python repository-file parser (AST-based).

Every ``.py`` file ingested — standalone or as part of a ``--recursive``
directory ingest (directory walking itself lives in
``kairos.services.ingest``, which dispatches each file to whichever parser's
``sniff`` matches) — gets: a module span, class/function spans with
line-range locators, and entities for module/class/function. Imports become
``imports`` derived relations from this file's module entity to the target
module entity; the target entity is created (or reused, via the ingest
service's cross-artifact entity dedup) purely by name; the connection
becomes meaningful once — and only once — a module of that name is
actually ingested. Nothing here waits for the whole batch to finish or
"guesses" at unresolved names.

A syntax error never drops the file: it still yields one file-level span
holding the raw source, tagged ``parse_status=failed`` with a diagnostic.
"""

from __future__ import annotations

import ast
from pathlib import Path

from kairos.domain.enums import (
    ArtifactKind,
    EntityType,
    Origin,
    ParseStatus,
    RelationPredicate,
    SpanKind,
)
from kairos.domain.ids import new_id
from kairos.domain.locators import RepoFileLinesLocator, locator_to_json
from kairos.domain.models import Diagnostic, Entity, Relation, SourceSpan
from kairos.domain.parser import ParseResult


def _line_range_locator(file_path: str, node: ast.AST) -> RepoFileLinesLocator:
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    return RepoFileLinesLocator(file_path=file_path, start_line=start, end_line=end)


class PythonParser:
    kind = ArtifactKind.REPOSITORY_FILE
    parser_name = "kairos.python_ast"
    parser_version = "1.0.0"

    def sniff(self, path: Path) -> bool:
        return path.suffix.lower() == ".py"

    def parse(self, path: Path, artifact_id: str) -> ParseResult:
        result = ParseResult()
        source = path.read_bytes().decode("utf-8", errors="replace")
        lines = source.splitlines()
        file_path_str = str(path)
        module_name = path.stem

        try:
            tree = ast.parse(source, filename=file_path_str)
        except SyntaxError as exc:
            module_span_id = new_id()
            locator = RepoFileLinesLocator(
                file_path=file_path_str, start_line=1, end_line=max(len(lines), 1)
            )
            result.spans.append(
                SourceSpan(
                    id=module_span_id,
                    artifact_id=artifact_id,
                    span_kind=SpanKind.FILE,
                    locator_json=locator_to_json(locator),
                    parent_span_id=None,
                    ordinal=0,
                    text_content=source,
                )
            )
            result.diagnostics.append(
                Diagnostic(message=f"Python syntax error: {exc.msg} at line {exc.lineno}")
            )
            result.parse_status = ParseStatus.FAILED
            return result

        module_span_id = new_id()
        module_locator = RepoFileLinesLocator(
            file_path=file_path_str, start_line=1, end_line=max(len(lines), 1)
        )
        module_entity_id = new_id()
        result.spans.append(
            SourceSpan(
                id=module_span_id,
                artifact_id=artifact_id,
                span_kind=SpanKind.MODULE,
                locator_json=locator_to_json(module_locator),
                parent_span_id=None,
                ordinal=0,
                text_content=ast.get_docstring(tree) or "",
            )
        )
        result.entities.append(
            Entity(
                id=module_entity_id,
                canonical_name=module_name,
                entity_type=EntityType.MODULE.value,
                origin=Origin.EXTRACTED,
            )
        )

        ordinal = [1]

        def visit_body(body: list[ast.stmt], parent_span_id: str) -> None:
            for node in body:
                if isinstance(node, ast.ClassDef):
                    span_id = new_id()
                    result.spans.append(
                        SourceSpan(
                            id=span_id,
                            artifact_id=artifact_id,
                            span_kind=SpanKind.CLASS_DEF,
                            locator_json=locator_to_json(_line_range_locator(file_path_str, node)),
                            parent_span_id=parent_span_id,
                            ordinal=ordinal[0],
                            text_content=ast.get_docstring(node) or node.name,
                        )
                    )
                    ordinal[0] += 1
                    result.entities.append(
                        Entity(
                            id=new_id(),
                            canonical_name=node.name,
                            entity_type=EntityType.CLASS_DEF.value,
                            origin=Origin.EXTRACTED,
                        )
                    )
                    visit_body(node.body, span_id)

                elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    span_id = new_id()
                    result.spans.append(
                        SourceSpan(
                            id=span_id,
                            artifact_id=artifact_id,
                            span_kind=SpanKind.FUNCTION_DEF,
                            locator_json=locator_to_json(_line_range_locator(file_path_str, node)),
                            parent_span_id=parent_span_id,
                            ordinal=ordinal[0],
                            text_content=ast.get_docstring(node) or node.name,
                        )
                    )
                    ordinal[0] += 1
                    result.entities.append(
                        Entity(
                            id=new_id(),
                            canonical_name=node.name,
                            entity_type=EntityType.FUNCTION_DEF.value,
                            origin=Origin.EXTRACTED,
                        )
                    )

                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        _emit_import(
                            result,
                            artifact_id,
                            file_path_str,
                            node,
                            parent_span_id,
                            module_entity_id,
                            ordinal,
                            alias.name.split(".")[0],
                        )

                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        _emit_import(
                            result,
                            artifact_id,
                            file_path_str,
                            node,
                            parent_span_id,
                            module_entity_id,
                            ordinal,
                            node.module.split(".")[0],
                        )

        visit_body(tree.body, module_span_id)
        result.parse_status = ParseStatus.OK
        return result


def _emit_import(
    result: ParseResult,
    artifact_id: str,
    file_path_str: str,
    node: ast.stmt,
    parent_span_id: str,
    module_entity_id: str,
    ordinal: list[int],
    target_module_name: str,
) -> None:
    span_id = new_id()
    result.spans.append(
        SourceSpan(
            id=span_id,
            artifact_id=artifact_id,
            span_kind=SpanKind.IMPORT,
            locator_json=locator_to_json(_line_range_locator(file_path_str, node)),
            parent_span_id=parent_span_id,
            ordinal=ordinal[0],
            text_content=target_module_name,
        )
    )
    ordinal[0] += 1
    target_entity_id = new_id()
    result.entities.append(
        Entity(
            id=target_entity_id,
            canonical_name=target_module_name,
            entity_type=EntityType.MODULE.value,
            origin=Origin.EXTRACTED,
        )
    )
    result.relations.append(
        Relation(
            id=new_id(),
            subject_id=module_entity_id,
            subject_kind="entity",
            predicate=RelationPredicate.IMPORTS.value,
            object_id=target_entity_id,
            object_kind="entity",
            evidence_span_id=span_id,
            origin=Origin.DERIVED,
            derivation_rule="python.import.v1",
            confidence=1.0,
        )
    )
