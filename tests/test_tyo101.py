"""
This file tests the TYO101 error: Unused remote imports

Some things to note: local/remote is a pretty arbitrary divide, and remote here really just means
not from the module our current working directory is in, or in the current working dir, but inside a venv.
"""
import textwrap

import pytest

from flake8_typing_only_imports.constants import TYO101
from tests import _get_error

examples = [
    # No error
    ('', set()),
    # Unused fake ast.Import
    ('import x', {'1:0 ' + TYO101.format(module='x')}),
    ('\nimport x', {'2:0 ' + TYO101.format(module='x')}),
    # Unused fake ast.ImportFrom
    ('from x import y', {'1:0 ' + TYO101.format(module='x.y')}),
    ('\n\nfrom x import y', {'3:0 ' + TYO101.format(module='x.y')}),
    # Unused venv ast.Import
    ('import pytest', {'1:0 ' + TYO101.format(module='pytest')}),
    ('\nimport pytest', {'2:0 ' + TYO101.format(module='pytest')}),
    # Unused venv ast.ImportFrom
    ('from _pytest import fixtures', {'1:0 ' + TYO101.format(module='_pytest.fixtures')}),
    ('\n\nfrom _pytest import fixtures', {'3:0 ' + TYO101.format(module='_pytest.fixtures')}),
    # Unused stdlib ast.Import
    ('import os', {'1:0 ' + TYO101.format(module='os')}),
    ('\nimport os', {'2:0 ' + TYO101.format(module='os')}),
    # Unused stdlib ast.ImportFrom
    ('from os import path', {'1:0 ' + TYO101.format(module='os.path')}),
    ('\n\nfrom os import path', {'3:0 ' + TYO101.format(module='os.path')}),
]


@pytest.mark.parametrize('example, expected', examples)
def test_tyo101_errors(example, expected):
    assert _get_error(example) == expected
