"""
File tests TC008:
    Type alias is wrapped in unnecessary quotes
"""

from __future__ import annotations

import sys
import textwrap

import pytest

from flake8_type_checking.constants import TC008
from tests.conftest import _get_error

examples = [
    ('', set()),
    ("x: TypeAlias = 'int'", {'1:15 ' + TC008.format(alias='int')}),
    # this should emit a TC010 instead
    ("x: TypeAlias = 'int' | None", set()),
    # this used to emit an error before fixing #164 if we wanted to handle
    # this case once again we could add a whitelist of subscriptable types
    ("x: TypeAlias = 'Dict[int]'", set()),
    ("from __future__ import annotations\nx: TypeAlias = 'int'", {'2:15 ' + TC008.format(alias='int')}),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict\nx: TypeAlias = 'Dict'", set()),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict\nx: TypeAlias = 'Dict[int]'", set()),
    (
        "from __future__ import annotations\nfrom typing import Dict\nx: TypeAlias = Dict['int']",
        {'3:20 ' + TC008.format(alias='int')},
    ),
    (
        "from __future__ import annotations\nif TYPE_CHECKING:\n\tfrom typing import Dict\nx: TypeAlias = Dict['int']",
        {'4:20 ' + TC008.format(alias='int')},
    ),
    (
        textwrap.dedent(
            '''
        from __future__ import annotations

        if TYPE_CHECKING:
            import something

        x: TypeAlias = "something"
        '''
        ),
        set(),
    ),
    (
        # Regression test for Issue #164
        textwrap.dedent(
            '''
        from wtforms import Field
        from wtforms.fields.core import UnboundField

        foo: TypeAlias = 'UnboundField[Field]'
        '''
        ),
        set(),
    ),
    (
        # this used to yield false negatives but works now, yay
        textwrap.dedent(
            '''
        class Foo(Protocol):
            pass

        x: TypeAlias = 'Foo | None'
        '''
        ),
        {'5:15 ' + TC008.format(alias='Foo | None')},
    ),
    (
        # Regression test for Issue #168
        textwrap.dedent(
            '''
        if TYPE_CHECKING:
            Foo: TypeAlias = str | int

        Bar: TypeAlias = 'Foo'
        '''
        ),
        set(),
    ),
    (
        # Regression test for Issue #168
        # The runtime declaration are inside a Protocol so they should not
        # affect the outcome
        textwrap.dedent(
            '''
        if TYPE_CHECKING:
            Foo: TypeAlias = str | int
        else:
            class X(Protocol):
                Foo: str | int

        Bar: TypeAlias = 'Foo'
        '''
        ),
        set(),
    ),
]

if sys.version_info >= (3, 12):
    examples.extend(
        [
            (
                # new style type alias should never be wrapped
                textwrap.dedent(
                    '''
                if TYPE_CHECKING:
                    type Foo = 'str'

                type Bar = 'Foo'
                '''
                ),
                {
                    '3:15 ' + TC008.format(alias='str'),
                    '5:11 ' + TC008.format(alias='Foo'),
                },
            )
        ]
    )


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC008_errors(example, expected):
    assert _get_error(example, error_code_filter='TC008') == expected
