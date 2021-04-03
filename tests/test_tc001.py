"""
This file tests the TC001 error:

    >> (Local) import should be moved to a type-checking block

One thing to note: The local/remote is a semi-arbitrary division and really just means

    1. Not from the module our current working directory is in, or
    2. In the current working dir, but inside a venv

"""
import textwrap

import pytest

from flake8_type_checking.constants import TC001
from tests import _get_error, mod

examples = [
    # No error
    ('', set()),
    # ------------------------------------------------------------------------------------
    # No usage whatsoever
    # ast.Import
    (f'import {mod}', {'1:0 ' + TC001.format(module=f'{mod}')}),
    (f'\nimport {mod}', {'2:0 ' + TC001.format(module=f'{mod}')}),
    # ast.ImportFrom
    (f'from {mod} import Plugin', {'1:0 ' + TC001.format(module=f'{mod}.Plugin')}),
    (f'\n\nfrom {mod} import constants', {'3:0 ' + TC001.format(module=f'{mod}.constants')}),
    # Aliased imports
    (f'import {mod} as x', {'1:0 ' + TC001.format(module=f'x')}),
    (f'from {mod} import constants as x', {'1:0 ' + TC001.format(module='x')}),
    # ------------------------------------------------------------------------------------
    # Imports used
    # ast.Import
    (f'import {mod}\nprint({mod})', set()),
    (f'\nimport {mod}\nx = {mod}.constants.TC001', set()),
    # ast.ImportFrom
    (f'from {mod} import Plugin\nx = Plugin()', set()),
    (f'\n\nfrom {mod} import constants\nx = constants.TC001[:1]', set()),
    # Aliased imports
    (f'import {mod} as x\ny = x', set()),
    (f'from {mod} import constants as x\nprint(x)', set()),
    # ------------------------------------------------------------------------------------
    # Imports used for ast.AnnAssign
    # ast.Import
    (f'import {mod}\nx: {mod}', {'1:0 ' + TC001.format(module=f'{mod}')}),
    (f'\nimport {mod}\nx: {mod} = 2', {'2:0 ' + TC001.format(module=f'{mod}')}),
    # ast.ImportFrom
    (f'from {mod} import Plugin\nx: Plugin', {'1:0 ' + TC001.format(module=f'{mod}.Plugin')}),
    (f'\n\nfrom {mod} import constants\nx: Plugin = 2', {'3:0 ' + TC001.format(module=f'{mod}.constants')}),
    # Aliased imports
    (f'import {mod} as x\ny: x', {'1:0 ' + TC001.format(module=f'x')}),
    (f'from {mod} import constants as x\ny: x = 2', {'1:0 ' + TC001.format(module='x')}),
    # ------------------------------------------------------------------------------------
    # Imports used for ast.arg annotation
    # ast.Import
    (f'import {mod}\ndef example(x: {mod}):\n\tpass', {'1:0 ' + TC001.format(module=f'{mod}')}),
    (f'\nimport {mod}\ndef example(x: {mod} = 2):\n\tpass', {'2:0 ' + TC001.format(module=f'{mod}')}),
    # ast.ImportFrom
    (f'from {mod} import Plugin\ndef example(x: Plugin):\n\tpass', {'1:0 ' + TC001.format(module=f'{mod}.Plugin')}),
    (
        f'\n\nfrom {mod} import constants\ndef example(x: Plugin = 2):\n\tpass',
        {'3:0 ' + TC001.format(module=f'{mod}.constants')},
    ),
    # Aliased imports
    (f'import {mod} as x\ndef example(y: x):\n\tpass', {'1:0 ' + TC001.format(module=f'x')}),
    (f'from {mod} import constants as x\ndef example(y: x = 2):\n\tpass', {'1:0 ' + TC001.format(module='x')}),
    # ------------------------------------------------------------------------------------
    # Imports used for returns annotation
    # ast.Import
    (f'import {mod}\ndef example() -> {mod}:\n\tpass', {'1:0 ' + TC001.format(module=f'{mod}')}),
    # ast.ImportFrom
    (f'from {mod} import Plugin\ndef example() -> Plugin:\n\tpass', {'1:0 ' + TC001.format(module=f'{mod}.Plugin')}),
    # Aliased imports
    (f'import {mod} as x\ndef example() -> x:\n\tpass', {'1:0 ' + TC001.format(module=f'x')}),
    (f'import {mod} as x\ndef example() -> x:\n\tpass', {'1:0 ' + TC001.format(module=f'x')}),
]


@pytest.mark.parametrize('example, expected', examples)
def test_TC001_errors(example, expected):
    assert _get_error(example) == expected
