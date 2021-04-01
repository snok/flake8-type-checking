import ast
from typing import Any, Generator, Tuple, Union

ImportType = Union[ast.Import, ast.ImportFrom]

Flake8Generator = Generator[Tuple[int, int, str, Any], None, None]
