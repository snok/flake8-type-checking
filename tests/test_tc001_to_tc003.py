"""
This file tests the TC001 error:

    >> (Application) import should be moved to a type-checking block

An application import is an import from the local project; i.e., not from a third party
library or builtin module. Application imports commonly create import circularity issues.
"""

from __future__ import annotations

import sys
import textwrap
from typing import List, Set, Tuple

import pytest

from flake8_type_checking.constants import TC001, TC002, TC003
from tests.conftest import _get_error, mod

L = List[Tuple[str, Set[str]]]


def get_tc_001_to_003_tests(import_: str, ERROR: str) -> L:
    """
    Return a generic list of asserts for each TC00[1-3] error.

    :param import_: The import to use for the examples.
    :param ERROR: The TC error to check for.
    """
    # No usage - these should all generate errors.
    no_use: L = [
        # ast.Import
        (f'import {import_}\nx:{import_}', {f"1:0 {ERROR.format(module=f'{import_}')}"}),
        (f'\nimport {import_}\nx:{import_}', {f"2:0 {ERROR.format(module=f'{import_}')}"}),
        # ast.ImportFrom
        (f'from {import_} import Plugin\nx:Plugin', {'1:0 ' + ERROR.format(module=f'{import_}.Plugin')}),
        (f'\n\nfrom {import_} import constants\nx:constants', {'3:0 ' + ERROR.format(module=f'{import_}.constants')}),
        # Aliased imports
        (f'import {import_} as x\ny:x', {'1:0 ' + ERROR.format(module='x')}),
        (f'from {import_} import constants as x\ny:x', {'1:0 ' + ERROR.format(module='x')}),
    ]

    # These imports are all used. None should generate errors.
    used: L = [
        # ast.Import
        (f'import {import_}\nprint({import_})', set()),
        (f'\nimport {import_}\nx = {import_}.constants.TC001', set()),
        # ast.ImportFrom
        (f'from {import_} import Plugin\nx = Plugin()', set()),
        (f'\n\nfrom {import_} import constants\nx = constants.TC001[:1]', set()),
        # Aliased imports
        (f'import {import_} as x\ny = x', set()),
        (f'from {import_} import constants as x\nprint(x)', set()),
    ]

    # Imports used for ast.AnnAssign. These should all generate errors, same as no use.
    used_for_annotations_only: L = [
        # ast.Import
        (f'import {import_}\nx: {import_}', {f"1:0 {ERROR.format(module=f'{import_}')}"}),
        (f'\nimport {import_}\nx: {import_} = 2', {f"2:0 {ERROR.format(module=f'{import_}')}"}),
        # ast.ImportFrom
        (f'from {import_} import Plugin\nx: Plugin', {'1:0 ' + ERROR.format(module=f'{import_}.Plugin')}),
        (
            f'\n\nfrom {import_} import constants\nx: constants = 2',
            {'3:0 ' + ERROR.format(module=f'{import_}.constants')},
        ),
        # Aliased imports
        (f'import {import_} as x\ny: x', {'1:0 ' + ERROR.format(module='x')}),
        (f'from {import_} import constants as x\ny: x = 2', {'1:0 ' + ERROR.format(module='x')}),
    ]

    # Imports used for ast.arg annotation. These should all generate errors, same as no use.
    used_for_arg_annotations_only: L = [
        # ast.Import
        (f'import {import_}\ndef example(x: {import_}):\n\tpass', {f"1:0 {ERROR.format(module=f'{import_}')}"}),
        (f'\nimport {import_}\ndef example(x: {import_} = 2):\n\tpass', {f"2:0 {ERROR.format(module=f'{import_}')}"}),
        # ast.ImportFrom
        (
            f'from {import_} import Plugin\ndef example(x: Plugin):\n\tpass',
            {'1:0 ' + ERROR.format(module=f'{import_}.Plugin')},
        ),
        (
            f'\n\nfrom {import_} import constants\ndef example(x: constants = 2):\n\tpass',
            {'3:0 ' + ERROR.format(module=f'{import_}.constants')},
        ),
        # Aliased imports
        (f'import {import_} as x\ndef example(y: x):\n\tpass', {'1:0 ' + ERROR.format(module='x')}),
        (f'from {import_} import constants as x\ndef example(y: x = 2):\n\tpass', {'1:0 ' + ERROR.format(module='x')}),
    ]

    # Imports used for returns annotation. These should all generate errors, same as no use.
    used_for_return_annotations_only: L = [
        # ast.Import
        (f'import {import_}\ndef example() -> {import_}:\n\tpass', {f"1:0 {ERROR.format(module=f'{import_}')}"}),
        # ast.ImportFrom
        (
            f'from {import_} import Plugin\ndef example() -> Plugin:\n\tpass',
            {'1:0 ' + ERROR.format(module=f'{import_}.Plugin')},
        ),
        # Aliased imports
        (f'import {import_} as x\ndef example() -> x:\n\tpass', {'1:0 ' + ERROR.format(module='x')}),
    ]

    used_for_type_alias_only: L = [
        (f'import {import_}\nx: TypeAlias = {import_}', {f"1:0 {ERROR.format(module=f'{import_}')}"}),
    ]

    if sys.version_info >= (3, 12):
        # new style type alias
        used_for_type_alias_only.append(
            (f'import {import_}\ntype x = {import_}', {f"1:0 {ERROR.format(module=f'{import_}')}"})
        )

    other_useful_test_cases: L = [
        (
            textwrap.dedent(f'''
                from {import_} import Dict, Any

                def example() -> Any:
                    return 1

                x: Dict[int] = 20
                '''),
            {'2:0 ' + ERROR.format(module=f'{import_}.Dict'), '2:0 ' + ERROR.format(module=f'{import_}.Any')},
        ),
        (
            textwrap.dedent('''
                from typing import TYPE_CHECKING

                if TYPE_CHECKING:
                    from typing import Dict

                x: Dict[int] = 20
                '''),
            set(),
        ),
        (
            textwrap.dedent('''
                from pathlib import Path

                class ImportVisitor(ast.NodeTransformer):

                    def __init__(self, cwd: Path) -> None:
                        # we need to know the current directory to guess at which imports are remote and which are not
                        self.cwd = cwd
                        origin = Path(spec.origin)

                class ExampleClass:

                    def __init__(self):
                        self.cwd = Path(pandas.getcwd())
                '''),
            set(),
        ),
        (
            textwrap.dedent(f'''
                import {import_}


                class Migration:
                    enum={import_}
                '''),
            set(),
        ),
        (
            textwrap.dedent(f'''
                import {import_}


                class Migration:
                    enum={import_}.EnumClass
                '''),
            set(),
        ),
        (
            textwrap.dedent(f'''
                from {import_} import y

                if TYPE_CHECKING:
                    _type = x
                else:
                    _type = y
                '''),
            set(),
        ),
        (
            textwrap.dedent(f'''
                from {import_} import y

                if TYPE_CHECKING:
                    _type = x
                elif True:
                    _type = y
                '''),
            set(),
        ),
    ]

    return [
        ('', set()),  # No code -> no error
        *no_use,
        *used,
        *used_for_annotations_only,
        *used_for_arg_annotations_only,
        *used_for_return_annotations_only,
        *used_for_type_alias_only,
        *other_useful_test_cases,
    ]


@pytest.mark.parametrize(('example', 'expected'), get_tc_001_to_003_tests(mod, TC001))
def test_TC001_errors(example: str, expected: set[str]) -> None:
    assert _get_error(example, error_code_filter='TC001') == expected


@pytest.mark.parametrize(('example', 'expected'), get_tc_001_to_003_tests('pandas', TC002))
def test_TC002_errors(example, expected):
    assert _get_error(example, error_code_filter='TC002') == expected


@pytest.mark.parametrize(('example', 'expected'), get_tc_001_to_003_tests('os', TC003))
def test_TC003_errors(example, expected):
    assert _get_error(example, error_code_filter='TC003') == expected
