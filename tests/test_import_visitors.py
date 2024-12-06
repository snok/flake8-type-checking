from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from flake8_type_checking.checker import ImportVisitor
from tests.conftest import REPO_ROOT

if TYPE_CHECKING:
    from typing import Callable, List, Tuple


def _visit(example: str) -> ImportVisitor:
    visitor = ImportVisitor(
        cwd=REPO_ROOT,
        pydantic_enabled=False,
        fastapi_enabled=False,
        fastapi_dependency_support_enabled=False,
        cattrs_enabled=False,
        sqlalchemy_enabled=False,
        sqlalchemy_mapped_dotted_names=[],
        injector_enabled=False,
        pydantic_enabled_baseclass_passlist=[],
    )
    visitor.visit(ast.parse(example.replace('; ', '\n')))
    return visitor


def _get_third_party_imports(example: str) -> list[str]:
    visitor = _visit(example)
    return list(visitor.third_party_imports.keys())


def _get_application_imports(example: str) -> list[str]:
    visitor = _visit(example)
    return list(visitor.application_imports.keys())


def _get_built_in_imports(example: str) -> list[str]:
    visitor = _visit(example)
    return list(visitor.built_in_imports.keys())


mod = 'flake8_type_checking'

f = _get_application_imports
application_imports = [
    # ast.Import
    (f'import {mod}', [f'{mod}'], f),
    (f'import {mod}.codes', [f'{mod}.codes'], f),
    (f'import {mod}.codes.TC001', [f'{mod}.codes.TC001'], f),
    # ast.ImportFrom
    (f'from {mod} import codes', [f'{mod}.codes'], f),
    (f'\nfrom {mod}.codes import TC001', [f'{mod}.codes.TC001'], f),
    # relative imports
    ('from . import codes', ['.codes'], f),
    ('\nfrom .codes import TC001', ['.codes.TC001'], f),
]

f = _get_built_in_imports
stdlib_imports = [
    # ast.Import
    ('import os', ['os'], f),
    ('import os.path', ['os.path'], f),
    ('import os.path.join', ['os.path.join'], f),
    # ast.ImportFrom
    ('from os import path', ['os.path'], f),
    ('from os.path import join', ['os.path.join'], f),
    ('\nfrom os.path import join', ['os.path.join'], f),
]

f = _get_third_party_imports
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

test_data = [*application_imports, *stdlib_imports, *venv_imports, *typing_block_imports]


@pytest.mark.parametrize(('example', 'result', 'loader'), test_data)
def test_find_imports(example: str, result: list[str], loader: Callable[[str], list[str]]) -> None:
    assert loader(example) == result, f'Failed for example: {example} and result: {result}'
