from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import ast
    import sys
    from typing import Any, Generator, Optional, Protocol, Tuple, TypedDict, Union

    class FunctionRangesDict(TypedDict):
        start: int
        end: int

    class FunctionScopeNamesDict(TypedDict):
        names: list[str]

    if sys.version_info >= (3, 12):
        Declaration = Union[ast.ClassDef, ast.AnnAssign, ast.Assign, ast.TypeAlias]
    else:
        Declaration = Union[ast.ClassDef, ast.AnnAssign, ast.Assign]
    Import = Union[ast.Import, ast.ImportFrom]
    Flake8Generator = Generator[Tuple[int, int, str, Any], None, None]

    class Name(Protocol):
        asname: Optional[str]
        name: str


ImportTypeValue = Literal['APPLICATION', 'THIRD_PARTY', 'BUILTIN', 'FUTURE']
