"""
File tests TC201:
    Annotation is wrapped in unnecessary quotes
"""

import sys
import textwrap

import pytest

from flake8_type_checking.constants import TC201
from tests.conftest import _get_error

examples = [
    ('', set()),
    ("x: 'int'", {'1:3 ' + TC201.format(annotation='int')}),
    # this used to emit an error before fixing #164 if we wanted to handle
    # this case once again we could add a whitelist of subscriptable types
    ("x: 'Dict[int]'", set()),
    ("from typing import Dict\nx: 'Dict'", {'2:3 ' + TC201.format(annotation='Dict')}),
    # this should emit a TC010 instead
    ("from typing import Dict\nx: 'Dict' | None", set()),
    ("from __future__ import annotations\nx: 'int'", {'2:3 ' + TC201.format(annotation='int')}),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict\nx: 'Dict'", set()),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict\nx: 'Dict[int]'", set()),
    (
        "from __future__ import annotations\nfrom typing import Dict\nx: Dict['int']",
        {'3:8 ' + TC201.format(annotation='int')},
    ),
    (
        "from __future__ import annotations\nif TYPE_CHECKING:\n\tfrom typing import Dict\nx: Dict['int']",
        {'4:8 ' + TC201.format(annotation='int')},
    ),
    (
        textwrap.dedent(
            '''
        from __future__ import annotations

        if TYPE_CHECKING:
            import something

        x: "something"
        '''
        ),
        set(),
    ),
    (
        textwrap.dedent(
            '''
        from __future__ import annotations

        if TYPE_CHECKING:
            import something

        def example(x: "something") -> something:
            pass
        '''
        ),
        set(),
    ),
    (
        textwrap.dedent(
            '''
        class X:
            def foo(self) -> 'X':
                pass
        '''
        ),
        set(),
    ),
    (
        textwrap.dedent(
            '''
        from __future__ import annotations
        class X:
            def foo(self) -> 'X':
                pass
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

        foo: 'UnboundField[Field]'
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

        x: 'Foo | None'
        '''
        ),
        {'5:3 ' + TC201.format(annotation='Foo | None')},
    ),
    (
        # Regression test for Issue #168
        textwrap.dedent(
            '''
        if TYPE_CHECKING:
            Foo = str | int
            Bar: TypeAlias = Foo | None
            T = TypeVar('T')
            Ts = TypeVarTuple('Ts')
            P = ParamSpec('P')

        x: 'Foo | None'
        y: 'Bar | None'
        Z: TypeAlias = 'Foo'

        def foo(a: 'T', *args: Unpack['Ts']) -> None:
            pass

        def bar(*args: 'P.args', **kwargs: 'P.kwargs') -> None:
            pass
        '''
        ),
        set(),
    ),
    (
        # Regression test for Issue #168
        # The runtime declarations are inside a different scope, so
        # they should not affect the outcome in the global scope
        # This used to raise errors for P.args and P.kwargs and
        # ideally it still would, but it would require more complex
        # logic in order to avoid false positives, so for now we
        # put up with the false negatives here
        textwrap.dedent(
            '''
        if TYPE_CHECKING:
            Foo = str | int
            Bar: TypeAlias = Foo | None
            T = TypeVar('T')
            Ts = TypeVarTuple('Ts')
            P = ParamSpec('P')
        else:
            class X(Protocol):
                Foo = str | int
                Bar: TypeAlias = Foo | None
                T = TypeVar('T')
                Ts = TypeVarTuple('Ts')
                P = ParamSpec('P')

        x: 'Foo | None'
        y: 'Bar | None'
        Z: TypeAlias = Foo

        def foo(a: 'T', *args: Unpack['Ts']) -> None:
            pass

        def bar(*args: 'P.args', **kwargs: 'P.kwargs') -> None:
            pass
        '''
        ),
        set(),
    ),
    (
        # Regression test for type checking only module attributes
        textwrap.dedent(
            '''
        import lxml.etree

        foo: 'lxml.etree._Element'
        '''
        ),
        set(),
    ),
    (
        # Regression test for #186
        textwrap.dedent(
            '''
        def foo(self) -> None:
            x: Bar
        '''
        ),
        set(),
    ),
    (
        # Reverse regression test for #186
        textwrap.dedent(
            '''
        def foo(self) -> None:
            x: 'Bar'
        '''
        ),
        {'3:7 ' + TC201.format(annotation='Bar')},
    ),
]

if sys.version_info >= (3, 12):
    # PEP695 tests
    examples += [
        (
            textwrap.dedent(
                """
            def foo[T](a: 'T') -> 'T':
                pass

            class Bar[T]:
                x: 'T'
            """
            ),
            {
                '2:14 ' + TC201.format(annotation='T'),
                '2:22 ' + TC201.format(annotation='T'),
                '6:7 ' + TC201.format(annotation='T'),
            },
        )
    ]


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC201_errors(example, expected):
    assert _get_error(example, error_code_filter='TC201') == expected
