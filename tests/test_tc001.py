"""
This file tests the TC001 error:

    >> (Application) import should be moved to a type-checking block

An application import is an import from the local project; i.e., not from a third party
library or builtin module. Application imports commonly create import circularity issues.
"""

from __future__ import annotations

from typing import List, Set, Tuple

import pytest

from flake8_type_checking.constants import TC001
from tests.conftest import _get_error, mod

L = List[Tuple[str, Set[str]]]

# No usage - these should all generate errors.
no_use: L = [
    # ast.Import
    (f'import {mod}', {f"1:0 {TC001.format(module=f'{mod}')}"}),
    (f'\nimport {mod}', {f"2:0 {TC001.format(module=f'{mod}')}"}),
    # ast.ImportFrom
    (f'from {mod} import Plugin', {'1:0 ' + TC001.format(module=f'{mod}.Plugin')}),
    (f'\n\nfrom {mod} import constants', {'3:0 ' + TC001.format(module=f'{mod}.constants')}),
    # Aliased imports
    (f'import {mod} as x', {'1:0 ' + TC001.format(module='x')}),
    (f'from {mod} import constants as x', {'1:0 ' + TC001.format(module='x')}),
]

# These imports are all used. None should generate errors.
used: L = [
    # ast.Import
    (f'import {mod}\nprint({mod})', set()),
    (f'\nimport {mod}\nx = {mod}.constants.TC001', set()),
    # ast.ImportFrom
    (f'from {mod} import Plugin\nx = Plugin()', set()),
    (f'\n\nfrom {mod} import constants\nx = constants.TC001[:1]', set()),
    # Aliased imports
    (f'import {mod} as x\ny = x', set()),
    (f'from {mod} import constants as x\nprint(x)', set()),
]

# Imports used for ast.AnnAssign. These should all generate errors, same as no use.
used_for_annotations_only: L = [
    # ast.Import
    (f'import {mod}\nx: {mod}', {f"1:0 {TC001.format(module=f'{mod}')}"}),
    (f'\nimport {mod}\nx: {mod} = 2', {f"2:0 {TC001.format(module=f'{mod}')}"}),
    # ast.ImportFrom
    (f'from {mod} import Plugin\nx: Plugin', {'1:0 ' + TC001.format(module=f'{mod}.Plugin')}),
    (f'\n\nfrom {mod} import constants\nx: Plugin = 2', {'3:0 ' + TC001.format(module=f'{mod}.constants')}),
    # Aliased imports
    (f'import {mod} as x\ny: x', {'1:0 ' + TC001.format(module='x')}),
    (f'from {mod} import constants as x\ny: x = 2', {'1:0 ' + TC001.format(module='x')}),
]

# Imports used for ast.arg annotation. These should all generate errors, same as no use.
used_for_arg_annotations_only: L = [
    # ast.Import
    (f'import {mod}\ndef example(x: {mod}):\n\tpass', {f"1:0 {TC001.format(module=f'{mod}')}"}),
    (f'\nimport {mod}\ndef example(x: {mod} = 2):\n\tpass', {f"2:0 {TC001.format(module=f'{mod}')}"}),
    # ast.ImportFrom
    (f'from {mod} import Plugin\ndef example(x: Plugin):\n\tpass', {'1:0 ' + TC001.format(module=f'{mod}.Plugin')}),
    (
        f'\n\nfrom {mod} import constants\ndef example(x: Plugin = 2):\n\tpass',
        {'3:0 ' + TC001.format(module=f'{mod}.constants')},
    ),
    # Aliased imports
    (f'import {mod} as x\ndef example(y: x):\n\tpass', {'1:0 ' + TC001.format(module='x')}),
    (f'from {mod} import constants as x\ndef example(y: x = 2):\n\tpass', {'1:0 ' + TC001.format(module='x')}),
]

# Imports used for returns annotation. These should all generate errors, same as no use.
used_for_return_annotations_only: L = [
    # ast.Import
    (f'import {mod}\ndef example() -> {mod}:\n\tpass', {f"1:0 {TC001.format(module=f'{mod}')}"}),
    # ast.ImportFrom
    (f'from {mod} import Plugin\ndef example() -> Plugin:\n\tpass', {'1:0 ' + TC001.format(module=f'{mod}.Plugin')}),
    # Aliased imports
    (f'import {mod} as x\ndef example() -> x:\n\tpass', {'1:0 ' + TC001.format(module='x')}),
]

examples: L = [
    ('', set()),  # No code -> no error
    *no_use,
    *used,
    *used_for_annotations_only,
    *used_for_arg_annotations_only,
    *used_for_return_annotations_only,
]


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC001_errors(example: str, expected: set[str]) -> None:
    assert _get_error(example) == expected
