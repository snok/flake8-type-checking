# flake8: noqa: D101
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ast
    from typing import Any, Generator, Tuple, TypedDict, Union

    class ErrorDict(TypedDict):
        error: str
        node: ast.AST

    class FunctionRangesDict(TypedDict):
        start: int
        end: int

    class FunctionScopeImportsDict(TypedDict):
        imports: list[str]

    Import = Union[ast.Import, ast.ImportFrom]
    Flake8Generator = Generator[Tuple[int, int, str, Any], None, None]
