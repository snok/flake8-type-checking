import ast
import os
from pathlib import Path
from typing import Optional

from flake8_type_checking.plugin import Plugin

REPO_ROOT = Path(os.getcwd()).parent
mod = 'flake8_type_checking'


def _get_error(example, error_code_filter: Optional[str] = None):
    os.chdir(REPO_ROOT)
    plugin = Plugin(ast.parse(example))
    errors = {f'{line}:{col} {msg}' for line, col, msg, _ in plugin.run()}
    if error_code_filter is None:
        error_code_filter = ''
    return {error for error in errors if error_code_filter in error}
