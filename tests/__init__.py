import ast
import os
from pathlib import Path
from typing import Optional
from unittest.mock import Mock

from flake8_type_checking.plugin import Plugin

REPO_ROOT = Path(os.getcwd()).parent
mod = 'flake8_type_checking'


def _get_error(example, error_code_filter: Optional[str] = None, **kwargs):
    os.chdir(REPO_ROOT)
    if error_code_filter:
        mock_options = Mock()
        mock_options.select = [error_code_filter]
        mock_options.extended_default_select = []
        mock_options.enable_extensions = []
        mock_options.type_checking_exempt_modules = []
        for k, v in kwargs.items():
            setattr(mock_options, k, v)
        plugin = Plugin(ast.parse(example), options=mock_options)
    else:
        plugin = Plugin(ast.parse(example))

    errors = {f'{line}:{col} {msg}' for line, col, msg, _ in plugin.run()}
    if error_code_filter is None:
        error_code_filter = ''
    return {error for error in errors if error_code_filter in error}
