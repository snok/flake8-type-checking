from __future__ import annotations

import ast
from typing import Callable, List, Tuple

import pytest

from flake8_type_checking.checker import ImportVisitor
from tests import REPO_ROOT


def _get_remote_imports(example):
    visitor = ImportVisitor(
        cwd=REPO_ROOT,
        pydantic_enabled=False,
        fastapi_enabled=False,
        fastapi_dependency_support_enabled=False,
        cattrs_enabled=False,
        pydantic_enabled_baseclass_passlist=[],
    )
    visitor.visit(ast.parse(example.replace('; ', '\n')))
    return list(visitor.remote_imports.keys())


def _get_local_imports(example):
    visitor = ImportVisitor(
        cwd=REPO_ROOT,
        pydantic_enabled=False,
        fastapi_enabled=False,
        fastapi_dependency_support_enabled=False,
        cattrs_enabled=False,
        pydantic_enabled_baseclass_passlist=[],
    )
    visitor.visit(ast.parse(example.replace('; ', '\n')))
    return list(visitor.local_imports.keys())


mod = 'flake8_type_checking'
f = _get_local_imports
local_imports = [
    # ast.Import
    (f'import {mod}', [f'{mod}'], f),
    (f'import {mod}.codes', [f'{mod}.codes'], f),
    (f'import {mod}.codes.TC001', [f'{mod}.codes.TC001'], f),
    # ast.ImportFrom
    (f'from {mod} import codes', [f'{mod}.codes'], f),
    (f'\nfrom {mod}.codes import TC001', [f'{mod}.codes.TC001'], f),
]

f = _get_remote_imports
stdlib_imports = [
    # ast.Import
    ('import os', ['os'], f),
    ('import os.path', ['os.path'], f),
    ('import os.path.join', ['os.path.join'], f),
    # ast.ImportFrom
    ('from _ import x', ['_.x'], f),
    ('from os import path', ['os.path'], f),
    ('from os.path import join', ['os.path.join'], f),
    ('\nfrom os.path import join', ['os.path.join'], f),
]
venv_imports = [
    # ast.Import
    ('import pytest', ['pytest'], f),
    ('import _pytest.fixtures', ['_pytest.fixtures'], f),
    ('import _pytest.config.argparsing', ['_pytest.config.argparsing'], f),
    # ast.ImportFrom
    ('from _pytest import fixtures', ['_pytest.fixtures'], f),
    ('from _pytest.config import argparsing', ['_pytest.config.argparsing'], f),
    ('\nfrom _pytest.config import argparsing', ['_pytest.config.argparsing'], f),
]

typing_block_imports: List[Tuple[str, list[str], Callable[[str], list[str]]]] = [
    (f'if TYPE_CHECKING:\n\t{example}', [], f)
    for _list in [stdlib_imports, venv_imports]
    for example, expected, f in _list[:-1]
]

test_data = [*local_imports, *stdlib_imports, *venv_imports, *typing_block_imports]


@pytest.mark.parametrize('example, result, loader', test_data)
def test_find_imports(example: str, result: list[str], loader: Callable[[str], list[str]]) -> None:
    assert loader(example) == result, f'Failed for example: {example} and result: {result}'
