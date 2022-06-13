"""
This file tests the TC002 error:

    >> Third-party import should be moved to a type-checking block

One thing to note: The third-party classification is a semi-arbitrary division and really just means

    1. From outside the module our current working directory is in, or
    2. Imported from a venv

"""

import textwrap

import pytest

from flake8_type_checking.constants import TC002
from tests.conftest import _get_error

examples = [
    # No error
    ('', set()),
    # ------------------------------------------------------------------------------------
    # No usage whatsoever
    # ast.Import
    ('import pandas', {'1:0 ' + TC002.format(module='pandas')}),
    ('\nimport pandas', {'2:0 ' + TC002.format(module='pandas')}),
    # ast.ImportFrom
    ('from pandas import path', {'1:0 ' + TC002.format(module='pandas.path')}),
    ('\n\nfrom pandas import path', {'3:0 ' + TC002.format(module='pandas.path')}),
    # Aliased imports
    ('import pandas as x', {'1:0 ' + TC002.format(module='x')}),
    ('from pandas import path as x', {'1:0 ' + TC002.format(module='x')}),
    # ------------------------------------------------------------------------------------
    # Imports used
    # ast.Import
    ('import pandas\nprint(pandas)', set()),
    ('\nimport pandas\nx = pandas.path', set()),
    # ast.ImportFrom
    ('from pandas import path\nx = path()', set()),
    ('\n\nfrom pandas import path\nx = path', set()),
    # Aliased imports
    ('import pandas as x\ny = x', set()),
    ('from pandas import path as x\nprint(x)', set()),
    # ------------------------------------------------------------------------------------
    # Imports used for ast.AnnAssign
    # ast.Import
    ('import pandas\nx: pandas', {'1:0 ' + TC002.format(module='pandas')}),
    ('\nimport pandas\nx: pandas = 2', {'2:0 ' + TC002.format(module='pandas')}),
    # ast.ImportFrom
    ('from pandas import path\nx: path', {'1:0 ' + TC002.format(module='pandas.path')}),
    ('\n\nfrom pandas import path\nx: path = 2', {'3:0 ' + TC002.format(module='pandas.path')}),
    # Aliased imports
    ('import pandas as x\ny: x', {'1:0 ' + TC002.format(module='x')}),
    ('from pandas import path as x\ny: x = 2', {'1:0 ' + TC002.format(module='x')}),
    # ------------------------------------------------------------------------------------
    # Imports used for ast.arg annotation
    # ast.Import
    ('import pandas\ndef example(x: pandas):\n\tpass', {'1:0 ' + TC002.format(module='pandas')}),
    ('\nimport pandas\ndef example(x: pandas = 2):\n\tpass', {'2:0 ' + TC002.format(module='pandas')}),
    # ast.ImportFrom
    ('from pandas import path\ndef example(x: path):\n\tpass', {'1:0 ' + TC002.format(module='pandas.path')}),
    ('\n\nfrom pandas import path\ndef example(x: path = 2):\n\tpass', {'3:0 ' + TC002.format(module='pandas.path')}),
    # Aliased imports
    ('import pandas as x\ndef example(y: x):\n\tpass', {'1:0 ' + TC002.format(module='x')}),
    ('from pandas import path as x\ndef example(y: x = 2):\n\tpass', {'1:0 ' + TC002.format(module='x')}),
    # ------------------------------------------------------------------------------------
    # Imports used for returns annotation
    # ast.Import
    ('import pandas\ndef example() -> pandas:\n\tpass', {'1:0 ' + TC002.format(module='pandas')}),
    # ast.ImportFrom
    ('from pandas import path\ndef example() -> path:\n\tpass', {'1:0 ' + TC002.format(module='pandas.path')}),
    # Aliased imports
    ('import pandas as x\ndef example() -> x:\n\tpass', {'1:0 ' + TC002.format(module='x')}),
    # ------------------------------------------------------------------------------------
    # Other useful test cases
    (
        textwrap.dedent(
            '''
            from x import Dict, Any

            def example() -> Any:
                return 1

            x: Dict[int] = 20
            '''
        ),
        {'2:0 ' + TC002.format(module='x.Dict'), '2:0 ' + TC002.format(module='x.Any')},
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
                    self.cwd = Path(pandas.getcwd())
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
            from x import Any, Generator, Union

            if TYPE_CHECKING:
                ImportType = Union[ast.Import, ast.ImportFrom]
                Flake8Generator = Generator[tuple[int, int, str, Any], None, None]
            '''
        ),
        {
            '2:0 ' + TC002.format(module='x.Any'),
            '2:0 ' + TC002.format(module='x.Generator'),
            '2:0 ' + TC002.format(module='x.Union'),
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
def test_TC002_errors(example, expected):
    assert _get_error(example, error_code_filter='TC002') == expected
