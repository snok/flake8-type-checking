"""
This file tests the TC010 error:

    >> Operands for | cannot be a string literal

"""

import sys
import textwrap

import pytest

from flake8_type_checking.constants import TC010
from tests.conftest import _get_error

examples = [
    # No error
    ('', set()),
    ('x: int | None', set()),
    # Used in type annotation at runtime
    (
        'x: "int" | None',
        {'1:3 ' + TC010},
    ),
    (
        'x: int | "None"',
        {'1:9 ' + TC010},
    ),
    (
        'x: "int" | "None"',
        {'1:3 ' + TC010, '1:11 ' + TC010},
    ),
    (
        'def foo(x: int | "str" | None) -> None: ...',
        {'1:17 ' + TC010},
    ),
    (
        'def foo(x: int) -> int | "None": ...',
        {'1:25 ' + TC010},
    ),
    # Used in implicit type alias at runtime (can't detect)
    (
        'x = "int" | None',
        set(),
    ),
    # Used in explicit type alias at runtime
    (
        'x: TypeAlias = "int" | None',
        {'1:15 ' + TC010},
    ),
    # Used in type annotations at type checking time
    # We could have chosen not to emit an error inside if TYPE_CHECKING blocks
    # however it is plausible that type checkers will be able to detect this
    # case at some point and then it might become an error, so it's better
    # to have cleaned up those annotations by then
    (
        textwrap.dedent("""
        if TYPE_CHECKING:
            x: "int" | None
            y: int | "None"
            z: "int" | "None"

            Foo: TypeAlias = "int" | None
            Bar = "int" | None

            def foo(x: int | "str" | None) -> int | "None":
                pass
        """),
        {
            '3:7 ' + TC010,
            '4:13 ' + TC010,
            '5:7 ' + TC010,
            '5:15 ' + TC010,
            '7:21 ' + TC010,
            '10:21 ' + TC010,
            '10:44 ' + TC010,
        },
    ),
]

if sys.version_info >= (3, 12):
    # PEP695 tests
    examples += [
        (
            'type x = "int" | None',
            {'1:9 ' + TC010},
        ),
    ]


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC010_errors(example, expected):
    assert _get_error(example, error_code_filter='TC010') == expected
