"""
This file tests the TC009 error:

    >> Move declaration out of type-checking block. Variable is used for more than type hinting.

"""
import sys
import textwrap

import pytest

from flake8_type_checking.constants import TC009
from tests.conftest import _get_error

examples = [
    # No error
    ('', set()),
    # Used in file
    (
        textwrap.dedent("""
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        datetime = Any

    x = datetime
    """),
        {'5:4 ' + TC009.format(name='datetime')},
    ),
    # Used in function
    (
        textwrap.dedent("""
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        class date: ...

    def example():
        return date()
    """),
        {'5:4 ' + TC009.format(name='date')},
    ),
    # Used, but only used inside the type checking block
    (
        textwrap.dedent("""
    if TYPE_CHECKING:
        class date: ...

        CustomType = date
    """),
        set(),
    ),
    # Used for typing only
    (
        textwrap.dedent("""
    if TYPE_CHECKING:
        class date: ...

    def example(*args: date, **kwargs: date):
        return

    my_type: Type[date] | date
    """),
        set(),
    ),
    (
        textwrap.dedent("""
    from __future__ import annotations

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        class AsyncIterator: ...


    class Example:

        async def example(self) -> AsyncIterator[list[str]]:
            yield 0
    """),
        set(),
    ),
    (
        textwrap.dedent("""
    from typing import TYPE_CHECKING
    from weakref import WeakKeyDictionary

    if TYPE_CHECKING:
        Any = str


    d = WeakKeyDictionary["Any", "Any"]()
    """),
        set(),
    ),
    (
        textwrap.dedent("""
    if TYPE_CHECKING:
        a = int
        b: TypeAlias = str
        class c(Protocol): ...
        class d(TypedDict): ...

    def test_function(a, /, b, *, c, **d):
        print(a, b, c, d)
    """),
        set(),
    ),
    # Regression test for #131
    # handle scopes correctly
    (
        textwrap.dedent("""
        if TYPE_CHECKING:
            Foo: something

        def foo():
            if TYPE_CHECKING:
                Foo: something_else
            else:
                Foo = object

            bar: Foo = Foo()
            return bar

        class X:
            if TYPE_CHECKING:
                class Foo(Protocol):
                    pass
            else:
                Foo = object

            bar: Foo = Foo()

    """),
        set(),
    ),
]

if sys.version_info >= (3, 12):
    examples.append(
        (
            textwrap.dedent("""
            if TYPE_CHECKING:
                type Foo = int

            x = Foo
            """),
            {'3:4 ' + TC009.format(name='Foo')},
        )
    )
    examples.append(
        (
            textwrap.dedent("""
            if TYPE_CHECKING:
                type Foo = int

            x: Foo
            """),
            set(),
        )
    )


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC009_errors(example, expected):
    assert _get_error(example, error_code_filter='TC009') == expected
