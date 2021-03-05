"""
File tests TYO201:
    Annotation should be wrapped in quotes
"""

import pytest

from flake8_typing_only_imports.constants import TYO200
from tests import _get_error

examples = [
    # # No error
    ('', set()),
    # # Basic ast.AnnAssign without need for futures import
    ('x: int', set()),
    # # Basic ast.AnnAssign where we should have a futures import
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\nx: Dict', {'0:0 ' + TYO200.format(annotation='Dict')}),
    ('if TYPE_CHECKING:\n\t\n\t\n\t\n\tfrom typing import Dict', {'0:0 ' + TYO200.format(annotation='Dict')}),
    ('if TYPE_CHECKING:\n\t\n\t\n\t\n\tx = 2', set()),
    ('if TYPE_CHECKING:\n\t\n\t\n\t\n\timport x', {'0:0 ' + TYO200.format(annotation='Dict')}),
    # Not much more point in testing this, as the logic is not dependent on the type of annotation assignments
    # it's purely concerned with whether an ast.Import or ast.ImportFrom exists within a type checking block
]


@pytest.mark.parametrize('example, expected', examples)
def test_tyo200_errors(example, expected):
    assert (
        _get_error(example) == expected
    ), f"No match for example: '{example}'. Found '{_get_error(example)}' instead of '{expected}'"
