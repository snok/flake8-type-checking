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
        textwrap.dedent('''
        from __future__ import annotations

        if TYPE_CHECKING:
            import something

        x: "something"
        '''),
        set(),
    ),
    (
        textwrap.dedent('''
        from __future__ import annotations

        if TYPE_CHECKING:
            import something

        def example(x: "something") -> something:
            pass
        '''),
        set(),
    ),
    (
        textwrap.dedent('''
        class X:
            def foo(self) -> 'X':
                pass
        '''),
        set(),
    ),
    (
        textwrap.dedent('''
        from __future__ import annotations
        class X:
            def foo(self) -> 'X':
                pass
        '''),
        set(),
    ),
    (
        # Regression test for Issue #164
        textwrap.dedent('''
        from wtforms import Field
        from wtforms.fields.core import UnboundField

        foo: 'UnboundField[Field]'
        '''),
        set(),
    ),
    (
        # avoid false positive for annotations that make
        # use of a newly defined class
        textwrap.dedent('''
        class Foo(Protocol):
            pass

        x: 'Foo | None'
        '''),
        set(),
    ),
    (
        # Regression test for Issue #168
        textwrap.dedent('''
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
        '''),
        set(),
    ),
    (
        # Inverse regression test for Issue #168
        # The declarations are inside a Protocol so they should not
        # count towards declarations inside a type checking block
        textwrap.dedent('''
        if TYPE_CHECKING:
            class X(Protocol):
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
        '''),
        {
            '10:3 ' + TC201.format(annotation='Foo | None'),
            '11:3 ' + TC201.format(annotation='Bar | None'),
            '12:15 ' + TC201.format(annotation='Foo'),
            '14:11 ' + TC201.format(annotation='T'),
            '14:30 ' + TC201.format(annotation='Ts'),
            '17:15 ' + TC201.format(annotation='P.args'),
            '17:35 ' + TC201.format(annotation='P.kwargs'),
        },
    ),
]

if sys.version_info >= (3, 12):
    examples.append(
        (
            # Regression test for Issue #168
            # using new type alias syntax
            textwrap.dedent('''
            if TYPE_CHECKING:
                type Foo = str | int

            x: 'Foo | None'
            type Z = 'Foo'
            '''),
            set(),
        )
    )


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC201_errors(example, expected):
    assert _get_error(example, error_code_filter='TC201') == expected
