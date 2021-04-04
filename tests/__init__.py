import ast
import os
from pathlib import Path
from typing import Optional
from unittest.mock import Mock

from flake8_type_checking.plugin import Plugin

REPO_ROOT = Path(os.getcwd()).parent
mod = 'flake8_type_checking'


def _get_error(example, error_code_filter: Optional[str] = None):
    os.chdir(REPO_ROOT)
    if error_code_filter:
        mock_options = Mock()
        mock_options.select = [error_code_filter]
        plugin = Plugin(ast.parse(example), options=mock_options)
    else:
        plugin = Plugin(ast.parse(example))

    errors = {f'{line}:{col} {msg}' for line, col, msg, _ in plugin.run()}
    if error_code_filter is None:
        error_code_filter = ''
    return {error for error in errors if error_code_filter in error}
