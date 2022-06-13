"""
This file tests the TC100 error:

    >> Missing 'from __future__ import annotations' import

The idea is that we should raise one of these errors if a file contains any type-checking imports and one is missing.

One thing to note: futures imports should always be at the top of a file, so we only need to check one line.
"""

import pytest

from flake8_type_checking.constants import TC100
from tests.conftest import _get_error, mod

examples = [
    # No errors
    ('', set()),
    ('if TYPE_CHECKING:\n\tx = 2', set()),
    # Unused import
    ('if TYPE_CHECKING:\n\tfrom typing import Dict', {'1:0 ' + TC100}),
    ('if TYPE_CHECKING:\n\tfrom typing import Dict, Any', {'1:0 ' + TC100}),
    (f'if TYPE_CHECKING:\n\timport {mod}', {'1:0 ' + TC100}),
    (f'if TYPE_CHECKING:\n\tfrom {mod} import constants', {'1:0 ' + TC100}),
    # Used imports
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\nx = Dict', set()),
    ('if TYPE_CHECKING:\n\tfrom typing import Dict, Any\nx, y = Dict, Any', set()),
    (f'if TYPE_CHECKING:\n\timport {mod}\nx = {mod}.constants.TC001', set()),
    (f'if TYPE_CHECKING:\n\tfrom {mod} import constants\nprint(constants)', set()),
    # Import used for AnnAssign
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\nx: Dict[str, int]', {'1:0 ' + TC100}),
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\nx: Dict[str, int] = {}', {'1:0 ' + TC100}),
    # Import used for arg
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\ndef example(x: Dict[str, int]):\n\tpass', {'1:0 ' + TC100}),
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\ndef example(x: Dict[str, int] = {}):\n\tpass', {'1:0 ' + TC100}),
    # Import used for returns
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\ndef example() -> Dict[str, int]:\n\tpass', {'1:0 ' + TC100}),
    # Probably not much point in adding many more test cases, as the logic for TC100
    # is not dependent on the type of annotation assignments; it's purely concerned with
    # whether an ast.Import or ast.ImportFrom exists within a type checking block
]


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC100_errors(example, expected):
    assert _get_error(example, error_code_filter='TC100') == expected
