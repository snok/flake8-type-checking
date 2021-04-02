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
from tests import _get_error

examples = [
    # No error
    ('', set()),
    # ------------------------------------------------------------------------------------
    # No usage whatsoever
    # ast.Import
    (f'import os', {'1:0 ' + TC002.format(module=f'os')}),
    (f'\nimport os', {'2:0 ' + TC002.format(module=f'os')}),
    # ast.ImportFrom
    (f'from os import path', {'1:0 ' + TC002.format(module=f'os.path')}),
    (f'\n\nfrom os import path', {'3:0 ' + TC002.format(module=f'os.path')}),
    # Aliased imports
    (f'import os as x', {'1:0 ' + TC002.format(module=f'x')}),
    (f'from os import path as x', {'1:0 ' + TC002.format(module='x')}),
    # ------------------------------------------------------------------------------------
    # Imports used
    # ast.Import
    (f'import os\nprint(os)', set()),
    (f'\nimport os\nx = os.path', set()),
    # ast.ImportFrom
    (f'from os import path\nx = path()', set()),
    (f'\n\nfrom os import path\nx = path', set()),
    # Aliased imports
    (f'import os as x\ny = x', set()),
    (f'from os import path as x\nprint(x)', set()),
    # ------------------------------------------------------------------------------------
    # Imports used for ast.AnnAssign
    # ast.Import
    (f'import os\nx: os', {'1:0 ' + TC002.format(module=f'os')}),
    (f'\nimport os\nx: os = 2', {'2:0 ' + TC002.format(module=f'os')}),
    # ast.ImportFrom
    (f'from os import path\nx: path', {'1:0 ' + TC002.format(module=f'os.path')}),
    (f'\n\nfrom os import path\nx: path = 2', {'3:0 ' + TC002.format(module=f'os.path')}),
    # Aliased imports
    (f'import os as x\ny: x', {'1:0 ' + TC002.format(module=f'x')}),
    (f'from os import path as x\ny: x = 2', {'1:0 ' + TC002.format(module='x')}),
    # ------------------------------------------------------------------------------------
    # Imports used for ast.arg annotation
    # ast.Import
    (f'import os\ndef example(x: os):\n\tpass', {'1:0 ' + TC002.format(module=f'os')}),
    (f'\nimport os\ndef example(x: os = 2):\n\tpass', {'2:0 ' + TC002.format(module=f'os')}),
    # ast.ImportFrom
    (f'from os import path\ndef example(x: path):\n\tpass', {'1:0 ' + TC002.format(module=f'os.path')}),
    (f'\n\nfrom os import path\ndef example(x: path = 2):\n\tpass', {'3:0 ' + TC002.format(module=f'os.path')}),
    # Aliased imports
    (f'import os as x\ndef example(y: x):\n\tpass', {'1:0 ' + TC002.format(module=f'x')}),
    (f'from os import path as x\ndef example(y: x = 2):\n\tpass', {'1:0 ' + TC002.format(module='x')}),
    # ------------------------------------------------------------------------------------
    # Imports used for returns annotation
    # ast.Import
    (f'import os\ndef example() -> os:\n\tpass', {'1:0 ' + TC002.format(module=f'os')}),
    # ast.ImportFrom
    (f'from os import path\ndef example() -> path:\n\tpass', {'1:0 ' + TC002.format(module=f'os.path')}),
    # Aliased imports
    (f'import os as x\ndef example() -> x:\n\tpass', {'1:0 ' + TC002.format(module=f'x')}),
    # ------------------------------------------------------------------------------------
    # Other useful test cases
    (
        textwrap.dedent(
            '''
            from typing import Dict, Any

            def example() -> Any:
                return 1

            x: Dict[int] = 20
            '''
        ),
        {'2:0 ' + TC002.format(module='typing.Dict'), '2:0 ' + TC002.format(module='typing.Any')},
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
                    self.cwd = cwd  # we need to know the current directory to guess at which imports are remote and which are not
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
]


@pytest.mark.parametrize('example, expected', examples)
def test_TC002_errors(example, expected):
    assert _get_error(example, error_code_filter='TC002') == expected
