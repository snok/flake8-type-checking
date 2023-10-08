"""
File tests TC007:
    Type alias should be wrapped in quotes
"""
import sys
import textwrap

import pytest

from flake8_type_checking.constants import TC007
from tests.conftest import _get_error

examples = [
    # No error
    ('', set()),
    ('x: TypeAlias = "int"', set()),
    ('from typing import Dict\nx: TypeAlias = Dict[int]', set()),
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\nx: TypeAlias = Dict', {'3:15 ' + TC007.format(alias='Dict')}),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict\nx: TypeAlias = 'Dict'", set()),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict as d\nx: TypeAlias = 'd[int]'", set()),
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\nx: TypeAlias = Dict[int]', {'3:15 ' + TC007.format(alias='Dict')}),
    # Regression test for issue #163
    (
        textwrap.dedent('''
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from collections.abc import Sequence
            from typing_extensions import TypeAlias

            Foo: TypeAlias = Sequence[int]
        '''),
        set(),
    ),
    # Inverse regression test for issue #163
    (
        textwrap.dedent('''
        from typing import TYPE_CHECKING
        from typing_extensions import TypeAlias

        if TYPE_CHECKING:
            from collections.abc import Sequence

        Foo: TypeAlias = Sequence[int]
        '''),
        {
            '8:17 ' + TC007.format(alias='Sequence'),
        },
    ),
]

if sys.version_info >= (3, 12):
    # RHS on an explicit TypeAlias with 3.12 syntax should not emit a TC107
    examples.append(
        (
            textwrap.dedent('''
            if TYPE_CHECKING:
                from collections.abc import Sequence

            type Foo = Sequence[int]
            '''),
            set(),
        )
    )


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC007_errors(example, expected):
    assert _get_error(example, error_code_filter='TC007') == expected
