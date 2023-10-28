"""
File tests TC200:
    Annotation should be wrapped in quotes
"""
import sys
import textwrap

import pytest

from flake8_type_checking.constants import TC200
from tests.conftest import _get_error

examples = [
    # No error
    ('', set()),
    ('x: int', set()),
    ('x: "int"', set()),
    ('from typing import Dict\nx: Dict[int]', set()),
    # Unused import/declaration
    ('if TYPE_CHECKING:\n\tfrom typing import Dict', set()),
    ('if TYPE_CHECKING:\n\tx = 2', set()),
    # Used import/declaration
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\nx: Dict = Dict()', set()),
    ('if TYPE_CHECKING:\n\tx = 2\ny = x + 2', set()),
    ('if TYPE_CHECKING:\n\tT = TypeVar("T")\nx: T\ny = T', set()),
    # Import/Declaration used only in annotation
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\nx: Dict', {'3:3 ' + TC200.format(annotation='Dict')}),
    ('if TYPE_CHECKING:\n\tT = TypeVar("T")\nx: T', {'3:3 ' + TC200.format(annotation='T')}),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict\nx: 'Dict'", set()),
    ('if TYPE_CHECKING:\n\tFoo: TypeAlias = Any\nx: Foo', {'3:3 ' + TC200.format(annotation='Foo')}),
    ("if TYPE_CHECKING:\n\tFoo: TypeAlias = Any\nx: 'Foo'", set()),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict as d\nx: 'd[int]'", set()),
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\nx: Dict[int]', {'3:3 ' + TC200.format(annotation='Dict')}),
    ('if TYPE_CHECKING:\n\timport something\nx: something', {'3:3 ' + TC200.format(annotation='something')}),
    (
        "if TYPE_CHECKING:\n\timport something\ndef example(x: 'something') -> something:\n\tpass",
        {'3:31 ' + TC200.format(annotation='something')},
    ),
    ("if TYPE_CHECKING:\n\timport something\ndef example(x: 'something') -> 'something':\n\tpass", set()),
    (
        (
            'from typing import Dict, TYPE_CHECKING\nif TYPE_CHECKING:\n\timport something\ndef example(x:'
            ' Dict[\'something\']) -> Dict[\'something\']:\n\tpass'
        ),
        set(),
    ),
    (
        textwrap.dedent('''
        from typing import Dict, TYPE_CHECKING

        if TYPE_CHECKING:
            import something

        def example(x: Dict[something]) -> Dict["something"]:
            pass
        '''),
        {'7:20 ' + TC200.format(annotation='something')},
    ),
    (
        textwrap.dedent('''
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            import ast

        def example(x: ast.If):
            pass
        '''),
        {'7:15 ' + TC200.format(annotation='ast')},
    ),
    # Regression test for issue #163
    (
        textwrap.dedent('''
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from collections.abc import Sequence
            from typing import NamedTuple, Protocol
            from typing_extensions import TypeAlias, TypedDict

            Foo: TypeAlias = Sequence[int]

            class FooTuple(NamedTuple):
                seq: Sequence[int]

            class FooProtocol(Protocol):
                seq: Sequence[int]

            class FooDict(TypedDict):
                seq: Sequence[int]
        '''),
        set(),
    ),
    # Inverse regression test for issue #163
    (
        textwrap.dedent('''
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from collections.abc import Sequence
            from typing import NamedTuple, Protocol
            from typing_extensions import TypeAlias, TypedDict

        Foo: TypeAlias = 'Sequence[int]'

        class FooTuple(NamedTuple):
            seq: Sequence[int]

        class FooProtocol(Protocol):
            seq: Sequence[int]

        class FooDict(TypedDict):
            seq: Sequence[int]

            if TYPE_CHECKING:
                # this should not count as a type checking global
                Bar: int

        x: Bar
        '''),
        {
            '9:5 ' + TC200.format(annotation='TypeAlias'),
            '12:9 ' + TC200.format(annotation='Sequence'),
            '15:9 ' + TC200.format(annotation='Sequence'),
            '18:9 ' + TC200.format(annotation='Sequence'),
        },
    ),
]

if sys.version_info >= (3, 12):
    # PEP695 tests
    examples += [
        (
            textwrap.dedent("""
            if TYPE_CHECKING:
                from .types import T

            def foo[T](a: T) -> T: ...

            type Foo[T] = T | None

            class Bar[T](Sequence[T]):
                x: T
            """),
            set(),
        )
    ]


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC200_errors(example, expected):
    assert _get_error(example, error_code_filter='TC200') == expected
