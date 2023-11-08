from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import ast
    from typing import Any, Generator, Optional, Protocol, Tuple, Union

    Function = Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda]
    Comprehension = Union[ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp]
    Import = Union[ast.Import, ast.ImportFrom]
    Flake8Generator = Generator[Tuple[int, int, str, Any], None, None]

    class Name(Protocol):
        asname: Optional[str]
        name: str

    class HasPosition(Protocol):
        @property
        def lineno(self) -> int:
            pass

        @property
        def col_offset(self) -> int:
            pass


ImportTypeValue = Literal['APPLICATION', 'THIRD_PARTY', 'BUILTIN', 'FUTURE']
