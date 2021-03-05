import ast
from typing import Any, Generator, Tuple, Union

ImportType = Union[ast.Import, ast.ImportFrom]

flake8_generator = Generator[Tuple[int, int, str, Any], None, None]
