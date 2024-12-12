"""
This file tests the TC100 error:

    >> Missing 'from __future__ import annotations' import

The idea is that we should raise one of these errors if a file contains any type-checking imports and one is missing.

One thing to note: futures imports should always be at the top of a file, so we only need to check one line.
"""

import sys
import textwrap

import pytest

from flake8_type_checking.constants import TC100
from tests.conftest import _get_error, mod

examples = [
    # No errors
    ('', set()),
    # Unused declaration
    ('if TYPE_CHECKING:\n\tx = 2', set()),
    # Used declaration
    ('if TYPE_CHECKING:\n\tx = 2\ny = x + 2', set()),
    ('if TYPE_CHECKING:\n\tT = TypeVar("T")\nx: T\ny = T', set()),
    # Declaration used only in annotation
    ('if TYPE_CHECKING:\n\tT = TypeVar("T")\nx: T', {'1:0 ' + TC100}),
    # Unused import
    ('if TYPE_CHECKING:\n\tfrom typing import Dict', set()),
    ('if TYPE_CHECKING:\n\tfrom typing import Dict, Any', set()),
    (f'if TYPE_CHECKING:\n\timport {mod}', set()),
    (f'if TYPE_CHECKING:\n\tfrom {mod} import constants', set()),
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
    (
        # Regression test for #186
        textwrap.dedent(
            '''
        if TYPE_CHECKING:
            from baz import Bar

        def foo(self) -> None:
            x: Bar
        '''
        ),
        set(),
    ),
]

if sys.version_info >= (3, 12):
    # PEP695 tests
    examples += [
        (
            textwrap.dedent(
                """
            if TYPE_CHECKING:
                from .types import T

            def foo[T](a: T) -> T: ...

            type Foo[T] = T | None

            class Bar[T](Sequence[T]):
                x: T
            """
            ),
            set(),
        )
    ]


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC100_errors(example, expected):
    assert _get_error(example, error_code_filter='TC100') == expected


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC100_errors_skipped_on_stubs(example, expected):
    assert _get_error(example, error_code_filter='TC100', filename='test.pyi') == set()
