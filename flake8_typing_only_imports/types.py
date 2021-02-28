import ast
from typing import TypedDict, Union


class ImportsContent(TypedDict):
    """Describes the content of self.import."""

    node: Union[ast.Import, ast.ImportFrom]
    error: str
