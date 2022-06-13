"""
This file tests the TC003 error:

    >> Built-in import should be moved to a type-checking block
"""
from __future__ import annotations

import textwrap
from typing import List, Set, Tuple

import pytest

from flake8_type_checking.constants import TC003
from tests.conftest import _get_error

L = List[Tuple[str, Set[str]]]

# No usage - these should all generate errors.
no_use: L = [
    # ast.Import
    ('import os', {'1:0 ' + TC003.format(module='os')}),
    ('\nimport os', {'2:0 ' + TC003.format(module='os')}),
    # ast.ImportFrom
    ('from os import path', {'1:0 ' + TC003.format(module='os.path')}),
    ('\n\nfrom os import path', {'3:0 ' + TC003.format(module='os.path')}),
    # Aliased imports
    ('import os as x', {'1:0 ' + TC003.format(module='x')}),
    ('from os import path as x', {'1:0 ' + TC003.format(module='x')}),
]

# These imports are all used. None should generate errors.
used: L = [
    # ast.Import
    ('import os\nprint(os)', set()),
    ('\nimport os\nx = os.path', set()),
    # ast.ImportFrom
    ('from os import path\nx = path()', set()),
    ('\n\nfrom os import path\nx = path', set()),
    # Aliased imports
    ('import os as x\ny = x', set()),
    ('from os import path as x\nprint(x)', set()),
]

# Imports used for ast.AnnAssign. These should all generate errors, same as no use.
used_for_annotations_only: L = [
    # ast.Import
    ('import os\nx: os', {'1:0 ' + TC003.format(module='os')}),
    ('\nimport os\nx: os = 2', {'2:0 ' + TC003.format(module='os')}),
    # ast.ImportFrom
    ('from os import path\nx: path', {'1:0 ' + TC003.format(module='os.path')}),
    ('\n\nfrom os import path\nx: path = 2', {'3:0 ' + TC003.format(module='os.path')}),
    # Aliased imports
    ('import os as x\ny: x', {'1:0 ' + TC003.format(module='x')}),
    ('from os import path as x\ny: x = 2', {'1:0 ' + TC003.format(module='x')}),
]

# Imports used for ast.arg annotation. These should all generate errors, same as no use.
used_for_arg_annotations_only: L = [
    # ast.Import
    ('import os\ndef example(x: os):\n\tpass', {'1:0 ' + TC003.format(module='os')}),
    ('\nimport os\ndef example(x: os = 2):\n\tpass', {'2:0 ' + TC003.format(module='os')}),
    # ast.ImportFrom
    ('from os import path\ndef example(x: path):\n\tpass', {'1:0 ' + TC003.format(module='os.path')}),
    ('\n\nfrom os import path\ndef example(x: path = 2):\n\tpass', {'3:0 ' + TC003.format(module='os.path')}),
    # Aliased imports
    ('import os as x\ndef example(y: x):\n\tpass', {'1:0 ' + TC003.format(module='x')}),
    ('from os import path as x\ndef example(y: x = 2):\n\tpass', {'1:0 ' + TC003.format(module='x')}),
]

# Imports used for returns annotation. These should all generate errors, same as no use.
used_for_return_annotations_only: L = [
    # ast.Import
    ('import os\ndef example() -> os:\n\tpass', {'1:0 ' + TC003.format(module='os')}),
    # ast.ImportFrom
    ('from os import path\ndef example() -> path:\n\tpass', {'1:0 ' + TC003.format(module='os.path')}),
    # Aliased imports
    ('import os as x\ndef example() -> x:\n\tpass', {'1:0 ' + TC003.format(module='x')}),
]

examples = [
    ('', set()),  # No code -> no error
    *no_use,
    *used,
    *used_for_annotations_only,
    *used_for_arg_annotations_only,
    *used_for_return_annotations_only,
    # Other useful test cases
    (
        textwrap.dedent(
            '''
            from os import Dict, Any

            def example() -> Any:
                return 1

            x: Dict[int] = 20
            '''
        ),
        {'2:0 ' + TC003.format(module='os.Dict'), '2:0 ' + TC003.format(module='os.Any')},
    ),
    (
        textwrap.dedent(
            '''
            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                from typing import Dict

            x: Dict[int] = 20
            '''
        ),
        set(),
    ),
    (
        textwrap.dedent(
            '''
            from pathlib import Path

            class ImportVisitor(ast.NodeTransformer):

                def __init__(self, cwd: Path) -> None:
                    # we need to know the current directory to guess at which imports are remote and which are not
                    self.cwd = cwd
                    origin = Path(spec.origin)

            class ExampleClass:

                def __init__(self):
                    self.cwd = Path(os.getcwd())
            '''
        ),
        set(),
    ),
    (
        textwrap.dedent(
            '''
            import proj.app.enums


            class Migration:
                enum=proj.app.enums
            '''
        ),
        set(),
    ),
    (
        textwrap.dedent(
            '''
            import proj.app.enums


            class Migration:
                enum=proj.app.enums.EnumClass
            '''
        ),
        set(),
    ),
    (
        textwrap.dedent(
            '''
            from os import Any, Generator, Union

            if TYPE_CHECKING:
                ImportType = Union[ast.Import, ast.ImportFrom]
                Flake8Generator = Generator[tuple[int, int, str, Any], None, None]
            '''
        ),
        {
            '2:0 ' + TC003.format(module='os.Any'),
            '2:0 ' + TC003.format(module='os.Generator'),
            '2:0 ' + TC003.format(module='os.Union'),
        },
    ),
    (
        textwrap.dedent(
            '''
            from x import y

            if TYPE_CHECKING:
                _type = x
            else:
                _type = y
            '''
        ),
        set(),
    ),
    (
        textwrap.dedent(
            '''
            from x import y

            if TYPE_CHECKING:
                _type = x
            elif True:
                _type = y
            '''
        ),
        set(),
    ),
]


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC003_errors(example, expected):
    assert _get_error(example, error_code_filter='TC003') == expected
