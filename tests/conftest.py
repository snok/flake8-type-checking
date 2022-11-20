from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from flake8_type_checking.plugin import Plugin

if TYPE_CHECKING:
    from typing import Any, Optional

REPO_ROOT = Path(__file__).parent.parent

mod = 'flake8_type_checking'


@pytest.fixture(autouse=True)
def _change_test_dir():
    os.chdir(REPO_ROOT / 'flake8_type_checking')
    yield
    os.chdir(REPO_ROOT)


def _get_error(example: str, *, error_code_filter: Optional[str] = None, **kwargs: Any) -> set[str]:
    os.chdir(REPO_ROOT)
    filename = kwargs.get('filename', 'test.py')
    if error_code_filter:
        mock_options = Mock()
        mock_options.select = [error_code_filter]
        mock_options.extend_select = None
        # defaults
        mock_options.extended_default_select = []
        mock_options.enable_extensions = []
        mock_options.type_checking_pydantic_enabled = False
        mock_options.type_checking_exempt_modules = []
        mock_options.type_checking_fastapi_enabled = False
        mock_options.type_checking_fastapi_dependency_support_enabled = False
        mock_options.type_checking_pydantic_enabled_baseclass_passlist = []
        mock_options.type_checking_strict = False
        # kwarg overrides
        for k, v in kwargs.items():
            setattr(mock_options, k, v)
        plugin = Plugin(ast.parse(example), options=mock_options, filename=filename)
    else:
        plugin = Plugin(ast.parse(example), filename=filename)

    errors = {f'{line}:{col} {msg}' for line, col, msg, _ in plugin.run()}
    if error_code_filter is None:
        error_code_filter = ''
    return {error for error in errors if any(error_code in error for error_code in error_code_filter.split(','))}
